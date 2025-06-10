import eventlet
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import time
import threading
import random

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
socketio = SocketIO(app)

GAME_WIDTH = 800
GAME_HEIGHT = 600
PADDLE_WIDTH = 100
PADDLE_HEIGHT = 15
BALL_RADIUS = 10
GAME_LOOP_INTERVAL_MS = 16
BALL_SPEED_BASE = 5

class Game:
    def __init__(self):
        self.levels = self.load_levels()
        self.level_index = 0
        self.reset_game()
        self._game_loop_thread = None

    def generate_brick_grid(self, rows, cols, start_x, start_y, brick_width, brick_height, spacing_x, spacing_y, pattern_fn):
        bricks = []
        for row in range(rows):
            for col in range(cols):
                x = start_x + col * (brick_width + spacing_x)
                y = start_y + row * (brick_height + spacing_y)
                breakable = pattern_fn(row, col)
                bricks.append({
                    'x': x,
                    'y': y,
                    'width': brick_width,
                    'height': brick_height,
                    'breakable': breakable
                })
        return bricks

    def random_brick_pattern(self, row, col, difficulty):
        chance_unbreakable = 0.05 + (0.03 * difficulty)
        return random.random() > chance_unbreakable

    def load_levels(self):
        return [
            self.generate_brick_grid(4, 13, 0, 0, 60, 20, 1, 1, lambda r, c: not (r == 0 and c % 3 == 0)),
            self.generate_brick_grid(6, 12, 0, 0, 50, 20, 1, 1, lambda r, c: (r + c) % 4 != 0),
            self.generate_brick_grid(3, 8, 0, 0, 70, 25, 1, 1, lambda r, c: True)
        ]

    def reset_game(self):
        self.player_paddle_x = (GAME_WIDTH - PADDLE_WIDTH) // 2
        self.ball_x = self.player_paddle_x + (PADDLE_WIDTH // 2)
        self.ball_y = GAME_HEIGHT - PADDLE_HEIGHT - BALL_RADIUS - 1
        self.ball_dx = 0
        self.ball_dy = 0
        self.score = 0
        self.game_over = False
        self.game_started = False
        difficulty = self.level_index
        cols = 14
        spacing_x = 1
        start_x = 1
        brick_width = int((GAME_WIDTH - start_x - spacing_x * (cols - 1)) / cols)
        self.bricks = self.generate_brick_grid(6, cols, start_x, 0, brick_width, 20, spacing_x, 1, lambda r, c: self.random_brick_pattern(r, c, difficulty))

    def get_game_state(self):
        return {
            'ball_x': self.ball_x,
            'ball_y': self.ball_y,
            'player_paddle_x': self.player_paddle_x,
            'score': self.score,
            'game_over': self.game_over,
            'game_started': self.game_started,
            'bricks': self.bricks
        }

    def update_game_state(self):
        if self.game_over or not self.game_started:
            return

        if not self.ball_moving:
            self.ball_x = self.player_paddle_x + (PADDLE_WIDTH // 2)
            self.ball_y = GAME_HEIGHT - PADDLE_HEIGHT - BALL_RADIUS - 1
            return

        self.move_ball_with_collisions()

        if all(not b['breakable'] for b in self.bricks):
            self.level_index = (self.level_index + 1) % len(self.levels)
            self.reset_game()

    def move_ball_with_collisions(self):
        steps = int(max(abs(self.ball_dx), abs(self.ball_dy)))
        dx_step = self.ball_dx / steps
        dy_step = self.ball_dy / steps

        for _ in range(steps):
            self.ball_x += dx_step
            self.ball_y += dy_step

            if self.ball_x - BALL_RADIUS < 0:
                self.ball_x = BALL_RADIUS
                self.ball_dx *= -1
                break
            elif self.ball_x + BALL_RADIUS > GAME_WIDTH:
                self.ball_x = GAME_WIDTH - BALL_RADIUS
                self.ball_dx *= -1
                break

            if self.ball_y - BALL_RADIUS < 0:
                self.ball_y = BALL_RADIUS
                self.ball_dy *= -1
                break

        if (self.ball_dy > 0 and self.ball_y + BALL_RADIUS >= GAME_HEIGHT - PADDLE_HEIGHT and self.ball_y + BALL_RADIUS <= GAME_HEIGHT - PADDLE_HEIGHT + abs(self.ball_dy)):
            if (self.ball_x + BALL_RADIUS > self.player_paddle_x and self.ball_x - BALL_RADIUS < self.player_paddle_x + PADDLE_WIDTH):
                self.ball_y = GAME_HEIGHT - PADDLE_HEIGHT - BALL_RADIUS
                ball_center_x_on_paddle = self.ball_x - self.player_paddle_x - (PADDLE_WIDTH / 2)
                normalized_impact = ball_center_x_on_paddle / (PADDLE_WIDTH / 2)
                deflection_factor = 3.0
                self.ball_dx = normalized_impact * deflection_factor
                if abs(self.ball_dx) < 1:
                    self.ball_dx = 1 if normalized_impact >= 0 else -1
                self.ball_dy *= -1
                self.score += 1

        if self.ball_y + BALL_RADIUS > GAME_HEIGHT:
            self.game_over = True
            self.game_started = False
            self.ball_moving = False

        new_bricks = []
        collision_happened = False

        for brick in self.bricks:
            if not collision_happened and self.check_collision_with_brick(brick):
                if brick['breakable']:
                    self.score += 5
                else:
                    new_bricks.append(brick)

                ball_center_x = self.ball_x
                ball_center_y = self.ball_y
                brick_center_x = brick['x'] + brick['width'] / 2
                brick_center_y = brick['y'] + brick['height'] / 2

                dx = abs(ball_center_x - brick_center_x)
                dy = abs(ball_center_y - brick_center_y)

                if dx > dy:
                    self.ball_dx *= -1
                else:
                    self.ball_dy *= -1

                collision_happened = True
            else:
                new_bricks.append(brick)

        self.bricks = new_bricks

        if all(not b['breakable'] for b in self.bricks):
            self.level_index = (self.level_index + 1) % len(self.levels)
            self.reset_game()
            self.game_started = False
            self.ball_moving = False

    def check_collision_with_brick(self, brick):
        ball_center_x = self.ball_x
        ball_center_y = self.ball_y
        ball_radius = BALL_RADIUS
        closest_x = max(brick['x'], min(ball_center_x, brick['x'] + brick['width']))
        closest_y = max(brick['y'], min(ball_center_y, brick['y'] + brick['height']))
        distance_x = ball_center_x - closest_x
        distance_y = ball_center_y - closest_y
        distance_squared = distance_x * distance_x + distance_y * distance_y
        return distance_squared < ball_radius * ball_radius

    def move_paddle(self, direction):
        if self.game_over:
            return

        PADDLE_MOVE_AMOUNT = 20

        if not self.ball_moving:
            if direction == 'left':
                self.player_paddle_x = max(0, self.player_paddle_x - PADDLE_MOVE_AMOUNT)
                self.ball_x = self.player_paddle_x + (PADDLE_WIDTH // 2)
            elif direction == 'right':
                self.player_paddle_x = min(GAME_WIDTH - PADDLE_WIDTH, self.player_paddle_x + PADDLE_MOVE_AMOUNT)
                self.ball_x = self.player_paddle_x + (PADDLE_WIDTH // 2)
        else:
            if direction == 'left':
                self.player_paddle_x = max(0, self.player_paddle_x - PADDLE_MOVE_AMOUNT)
            elif direction == 'right':
                self.player_paddle_x = min(GAME_WIDTH - PADDLE_WIDTH, self.player_paddle_x + PADDLE_MOVE_AMOUNT)

    def start_game_loop(self):
        if self._game_loop_thread is None or not self._game_loop_thread.is_alive():
            self._game_loop_thread = threading.Thread(target=self._game_loop_run)
            self._game_loop_thread.daemon = True
            self._game_loop_thread.start()

    def _game_loop_run(self):
        while not self.game_over:
            start_time = time.time()
            self.update_game_state()
            socketio.emit('game_state', self.get_game_state())
            elapsed_time_ms = (time.time() - start_time) * 1000
            sleep_time = (GAME_LOOP_INTERVAL_MS - elapsed_time_ms) / 1000.0
            if sleep_time > 0:
                time.sleep(sleep_time)

game = Game()

@app.route('/')
def index():
    return render_template('index.html', game_width=GAME_WIDTH, game_height=GAME_HEIGHT)

@socketio.on('connect')
def test_connect():
    print('Client connected')
    emit('game_state', game.get_game_state())

@socketio.on('disconnect')
def test_disconnect():
    print('Client disconnected')

@socketio.on('move_paddle')
def handle_paddle_move(data):
    direction = data['direction']
    game.move_paddle(direction)

@socketio.on('start_game')
def handle_start_game():
    if not game.game_started:
        if game.game_over:
            game.reset_game()
        game.game_started = True
        game.ball_moving = True
        game.ball_dx = 3 if game.ball_x < GAME_WIDTH // 2 else -3
        game.ball_dy = -3
        game.start_game_loop()
        emit('game_state', game.get_game_state())

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True, port=5000, use_reloader=False)
