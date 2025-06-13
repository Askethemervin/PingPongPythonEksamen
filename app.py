import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import time
import threading
import random
import uuid # For unique IDs for power-ups

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

# Power-up specific constants
POWER_UP_FALL_SPEED = 2
POWER_UP_RADIUS = 15 # For collision detection
PADDLE_ENLARGE_DURATION_SECONDS = 20
PADDLE_ENLARGE_FACTOR = 1.5
BALL_SLOW_DURATION_SECONDS = 10
BALL_SLOW_FACTOR = 0.5


class Game:
    def __init__(self):
        self.levels = self.load_levels()
        self.level_index = 0
        self.reset_game()
        self._game_loop_thread = None
        self.power_ups = []
        self.active_power_ups = {} # Track active power-ups and their end times

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
        self.current_paddle_width = PADDLE_WIDTH # Track current paddle width
        self.ball_x = self.player_paddle_x + (self.current_paddle_width // 2) # Use current paddle width
        self.ball_y = GAME_HEIGHT - PADDLE_HEIGHT - BALL_RADIUS - 1
        self.ball_dx = 0
        self.ball_dy = 0
        self.current_ball_speed = BALL_SPEED_BASE # Track current ball speed
        self.score = 0
        self.game_over = False
        self.game_started = False
        self.ball_moving = False # New flag to control ball movement when game is not started
        self.power_ups = [] # Clear power-ups on reset
        self.active_power_ups = {} # Clear active power-ups

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
            'player_paddle_width': self.current_paddle_width, # Send current paddle width
            'score': self.score,
            'game_over': self.game_over,
            'game_started': self.game_started,
            'bricks': self.bricks,
            'power_ups': self.power_ups # Include power-ups in game state
        }

    def update_game_state(self):
        self.check_active_power_ups() # Check for expired power-ups

        if self.game_over or not self.game_started:
            return

        if not self.ball_moving:
            self.ball_x = self.player_paddle_x + (self.current_paddle_width // 2)
            self.ball_y = GAME_HEIGHT - PADDLE_HEIGHT - BALL_RADIUS - 1
            return

        self.move_ball_with_collisions()
        self.move_power_ups()
        self.check_power_up_collisions()

        if all(not b['breakable'] for b in self.bricks):
            self.level_index = (self.level_index + 1) % len(self.levels)
            self.reset_game()
            self.game_started = False
            self.ball_moving = False

    def move_ball_with_collisions(self):
        # Calculate effective speed for step determination
        effective_speed_x = abs(self.ball_dx) * self.current_ball_speed / BALL_SPEED_BASE
        effective_speed_y = abs(self.ball_dy) * self.current_ball_speed / BALL_SPEED_BASE

        # Determine number of steps based on the maximum component speed
        steps = int(max(effective_speed_x, effective_speed_y)) + 1 
        
        if steps == 0: 
            return

        # Calculate step increments, scaled by current_ball_speed
        dx_step = self.ball_dx / steps * (self.current_ball_speed / BALL_SPEED_BASE)
        dy_step = self.ball_dy / steps * (self.current_ball_speed / BALL_SPEED_BASE)

        for _ in range(steps):
            self.ball_x += dx_step
            self.ball_y += dy_step

            # Wall collisions
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

            # Paddle collision
            if (self.ball_dy > 0 and 
                self.ball_y + BALL_RADIUS >= GAME_HEIGHT - PADDLE_HEIGHT and 
                # Check if ball has potential to hit in this step
                self.ball_y + BALL_RADIUS <= GAME_HEIGHT - PADDLE_HEIGHT + abs(dy_step) + 1 and 
                self.ball_x + BALL_RADIUS > self.player_paddle_x and 
                self.ball_x - BALL_RADIUS < self.player_paddle_x + self.current_paddle_width):
                
                self.ball_y = GAME_HEIGHT - PADDLE_HEIGHT - BALL_RADIUS 
                ball_center_x_on_paddle = self.ball_x - self.player_paddle_x - (self.current_paddle_width / 2)
                normalized_impact = ball_center_x_on_paddle / (self.current_paddle_width / 2)
                deflection_factor = 3.0
                self.ball_dx = normalized_impact * deflection_factor
                if abs(self.ball_dx) < 1:
                    self.ball_dx = 1 if normalized_impact >= 0 else -1
                self.ball_dy *= -1
                self.score += 1
                break 

        # Game over condition (checked after all steps or collision break)
        if self.ball_y + BALL_RADIUS > GAME_HEIGHT:
            self.game_over = True
            self.game_started = False
            self.ball_moving = False

        # Brick collisions
        new_bricks = []
        
        for brick in self.bricks:
            if self.check_collision_with_brick(brick):
                if brick['breakable']:
                    self.score += 5
                    self.spawn_power_up(brick['x'] + brick['width'] / 2, brick['y'] + brick['height'] / 2)
                else:
                    new_bricks.append(brick)

                # Determine collision side for more accurate reflection
                # Calculate overlap on X and Y axes
                overlap_x = (BALL_RADIUS + brick['width'] / 2) - abs(self.ball_x - (brick['x'] + brick['width'] / 2))
                overlap_y = (BALL_RADIUS + brick['height'] / 2) - abs(self.ball_y - (brick['y'] + brick['height'] / 2))

                if overlap_x > 0 and overlap_y > 0: # There is an actual overlap
                    if overlap_x < overlap_y: # Collision was primarily horizontal
                        self.ball_dx *= -1
                        # Adjust ball position to prevent sticking
                        if self.ball_x < brick['x'] + brick['width'] / 2: # Hit left side
                            self.ball_x = brick['x'] - BALL_RADIUS
                        else: # Hit right side
                            self.ball_x = brick['x'] + brick['width'] + BALL_RADIUS
                    else: # Collision was primarily vertical
                        self.ball_dy *= -1
                        # Adjust ball position to prevent sticking
                        if self.ball_y < brick['y'] + brick['height'] / 2: # Hit top
                            self.ball_y = brick['y'] - BALL_RADIUS
                        else: # Hit bottom
                            self.ball_y = brick['y'] + brick['height'] + BALL_RADIUS
            else:
                new_bricks.append(brick)

        self.bricks = new_bricks

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
                self.ball_x = self.player_paddle_x + (self.current_paddle_width // 2)
            elif direction == 'right':
                self.player_paddle_x = min(GAME_WIDTH - self.current_paddle_width, self.player_paddle_x + PADDLE_MOVE_AMOUNT)
                self.ball_x = self.player_paddle_x + (self.current_paddle_width // 2)
        else:
            if direction == 'left':
                self.player_paddle_x = max(0, self.player_paddle_x - PADDLE_MOVE_AMOUNT)
            elif direction == 'right':
                self.player_paddle_x = min(GAME_WIDTH - self.current_paddle_width, self.player_paddle_x + PADDLE_MOVE_AMOUNT)


    # --- Power-up related functions ---
    def spawn_power_up(self, x, y):
        if random.random() < 0.3: # 30% chance to drop a power-up
            power_up_type = random.choice(['slow_ball', 'enlarge_paddle'])
            self.power_ups.append({
                'id': str(uuid.uuid4()), # Unique ID for each power-up
                'type': power_up_type,
                'x': x - POWER_UP_RADIUS, # Center the power-up
                'y': y - POWER_UP_RADIUS,
                'radius': POWER_UP_RADIUS
            })

    def move_power_ups(self):
        for pu in self.power_ups:
            pu['y'] += POWER_UP_FALL_SPEED
            # Remove power-ups that fall off screen
        self.power_ups = [pu for pu in self.power_ups if pu['y'] < GAME_HEIGHT]

    def check_power_up_collisions(self):
        collected_power_ups = []
        for pu in self.power_ups:
            # Check collision with paddle
            if (pu['y'] + pu['radius'] > GAME_HEIGHT - PADDLE_HEIGHT and
                pu['y'] - pu['radius'] < GAME_HEIGHT and
                pu['x'] + pu['radius'] > self.player_paddle_x and
                pu['x'] - pu['radius'] < self.player_paddle_x + self.current_paddle_width): # Use current_paddle_width

                collected_power_ups.append(pu)
                self.apply_power_up(pu)

        # Remove collected power-ups
        self.power_ups = [pu for pu in self.power_ups if pu not in collected_power_ups]

    def apply_power_up(self, power_up):
        current_time = time.time()
        if power_up['type'] == 'slow_ball':
            print("Applying slow_ball power-up!")
            self.current_ball_speed = BALL_SPEED_BASE * BALL_SLOW_FACTOR
            self.active_power_ups['slow_ball'] = current_time + BALL_SLOW_DURATION_SECONDS
        elif power_up['type'] == 'enlarge_paddle':
            print("Applying enlarge_paddle power-up!")
            self.current_paddle_width = PADDLE_WIDTH * PADDLE_ENLARGE_FACTOR
            # Adjust paddle position if it goes off-screen after enlarging
            self.player_paddle_x = min(GAME_WIDTH - self.current_paddle_width, self.player_paddle_x)
            self.active_power_ups['enlarge_paddle'] = current_time + PADDLE_ENLARGE_DURATION_SECONDS

    def check_active_power_ups(self):
        current_time = time.time()
        expired_power_ups = []
        for pu_type, end_time in self.active_power_ups.items():
            if current_time >= end_time:
                expired_power_ups.append(pu_type)

        for pu_type in expired_power_ups:
            print(f"Power-up {pu_type} expired.")
            if pu_type == 'slow_ball':
                self.current_ball_speed = BALL_SPEED_BASE
            elif pu_type == 'enlarge_paddle':
                self.current_paddle_width = PADDLE_WIDTH
            del self.active_power_ups[pu_type]

    # --- End of Power-up related functions ---


    def start_game_loop(self):
        if self._game_loop_thread is None or not self._game_loop_thread.is_alive():
            self._game_loop_thread = threading.Thread(target=self._game_loop_run)
            self._game_loop_thread.daemon = True
            self._game_loop_thread.start()

    def _game_loop_run(self):
        while not self.game_over:
            start_time = time.time()
            self.update_game_state()
            socketio.emit('game_state', game.get_game_state())
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
        # Ensure initial ball speed is based on BALL_SPEED_BASE
        game.ball_dx = (BALL_SPEED_BASE // 2) if game.ball_x < GAME_WIDTH // 2 else -(BALL_SPEED_BASE // 2)
        game.ball_dy = -BALL_SPEED_BASE
        game.start_game_loop()
        emit('game_state', game.get_game_state())

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True, port=5000, use_reloader=False)