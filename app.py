from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import time
import threading
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here' # Husk at ændre dette til en rigtig hemmelig nøgle i et rigtigt projekt!
socketio = SocketIO(app)

# --- Spilindstillinger ---
GAME_WIDTH = 800
GAME_HEIGHT = 600
PADDLE_WIDTH = 100
PADDLE_HEIGHT = 15
BALL_RADIUS = 10
GAME_LOOP_INTERVAL_MS = 16 # Ca. 60 FPS (1000ms / 60)

# --- Spillets tilstand ---
class Game:
    def __init__(self):
        self.levels = self.load_levels()
        self.level_index = 0
        self.reset_game()
        self._game_loop_thread = None # Tråden til spil-logikken

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
            self.generate_brick_grid(
                rows=4, cols=13,
                start_x=0, start_y=50,
                brick_width=60,
                brick_height=20,
                spacing_x=1,
                spacing_y=5,
                pattern_fn=lambda r, c: not (r == 0 and c % 3 == 0)
            ),
            self.generate_brick_grid(
                rows=6, cols=12,
                start_x=30, start_y=40,
                brick_width=50, brick_height=20,
                spacing_x=4, spacing_y=4,
                pattern_fn=lambda r, c: (r + c) % 4 != 0
            ),
            self.generate_brick_grid(
                rows=3, cols=8,
                start_x=100, start_y=70,
                brick_width=70, brick_height=25,
                spacing_x=6, spacing_y=6,
                pattern_fn=lambda r, c: True
            )
        ]


    def reset_game(self):
        self.ball_x = GAME_WIDTH // 2
        self.ball_y = GAME_HEIGHT // 2
        self.ball_dx = 5  # Hastighed i x-retning
        self.ball_dy = 5  # Hastighed i y-retning (initialt nedad)

        self.player_paddle_x = (GAME_WIDTH - PADDLE_WIDTH) // 2
        self.score = 0
        self.game_over = False
        self.game_started = False # Ny flag for at styre start
        difficulty = self.level_index
        self.bricks = self.generate_brick_grid(
            rows=5,
            cols=13,
            start_x=0,
            start_y=50,
            brick_width=60,
            brick_height=20,
            spacing_x=1,
            spacing_y=5,
            pattern_fn=lambda r, c: self.random_brick_pattern(r, c, difficulty)
        )

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

        # Flyt bolden
        self.ball_x += self.ball_dx
        self.ball_y += self.ball_dy

        # Kollision med vægge (venstre/højre)
        if self.ball_x - BALL_RADIUS < 0 or self.ball_x + BALL_RADIUS > GAME_WIDTH:
            self.ball_dx *= -1 # Vend x-retning

        # Kollision med topvæggen
        if self.ball_y - BALL_RADIUS < 0:
            self.ball_dy *= -1 # Vend y-retning

        # Kollision med spillerens paddle
        # Check om bolden er ved paddle's y-niveau ELLER lige over den
        if (self.ball_y + BALL_RADIUS >= GAME_HEIGHT - PADDLE_HEIGHT and
            self.ball_y + BALL_RADIUS <= GAME_HEIGHT): # Tjek for at fange bolden kun når den er ved bunden
            # Check om boldens x-position er inden for paddle's x-område
            if (self.ball_x + BALL_RADIUS > self.player_paddle_x and
                self.ball_x - BALL_RADIUS < self.player_paddle_x + PADDLE_WIDTH):
                self.ball_dy *= -1 # Vend y-retning
                self.score += 1

        # Bolden passerer forbi paddle'en (Game Over)
        if self.ball_y + BALL_RADIUS > GAME_HEIGHT:
            self.game_over = True
            self.game_started = False # Spillet stopper

        remaining_bricks = []
        for brick in self.bricks:
            if self.check_collision_with_brick(brick):
                if brick['breakable']:
                    self.score += 5
                else:
                    remaining_bricks.append(brick)
                self.ball_dy *= -1
            else:
                remaining_bricks.append(brick)

        self.bricks = remaining_bricks
            
        if all(not b['breakable'] for b in self.bricks):
            self.level_index = (self.level_index + 1) % len(self.levels)
            self.reset_game()
        
    def check_collision_with_brick(self, brick):
        bx, by = self.ball_x, self.ball_y
        r = BALL_RADIUS
        return (
            bx + r > brick['x'] and
            bx - r < brick['x'] + brick['width'] and
            by + r > brick['y'] and
            by - r < brick['y'] + brick['height']
        )

    def move_paddle(self, direction):
        if self.game_over:
            return

        if direction == 'left':
            self.player_paddle_x = max(0, self.player_paddle_x - 20) # Flyt med 20 pixels
        elif direction == 'right':
            self.player_paddle_x = min(GAME_WIDTH - PADDLE_WIDTH, self.player_paddle_x + 20) # Flyt med 20 pixels

    def start_game_loop(self):
        if self._game_loop_thread is None or not self._game_loop_thread.is_alive():
            self._game_loop_thread = threading.Thread(target=self._game_loop_run)
            self._game_loop_thread.daemon = True # Gør tråden til en dæmon, så den lukker med hovedprogrammet
            self._game_loop_thread.start()

    def _game_loop_run(self):
        while not self.game_over: # Løb indtil spillet er slut
            start_time = time.time()
            self.update_game_state()
            socketio.emit('game_state', self.get_game_state()) # Send opdateret tilstand til klienten

            elapsed_time_ms = (time.time() - start_time) * 1000
            sleep_time = (GAME_LOOP_INTERVAL_MS - elapsed_time_ms) / 1000.0
            if sleep_time > 0:
                time.sleep(sleep_time)

# Opret en global instans af spillet
game = Game()

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html', game_width=GAME_WIDTH, game_height=GAME_HEIGHT)

# --- SocketIO Events ---
@socketio.on('connect')
def test_connect():
    print('Client connected')
    emit('game_state', game.get_game_state()) # Send initial tilstand ved forbindelse

@socketio.on('disconnect')
def test_disconnect():
    print('Client disconnected')

@socketio.on('move_paddle')
def handle_paddle_move(data):
    direction = data['direction']
    game.move_paddle(direction)
    # Ingen grund til at sende game_state her, da game loop'en allerede gør det.

@socketio.on('start_game')
def handle_start_game():
    if not game.game_started and game.game_over: # Nulstil kun hvis spillet er slut
        game.reset_game()
    game.game_started = True
    game.start_game_loop()
    emit('game_state', game.get_game_state()) # Send den nulstillede/startede tilstand

if __name__ == '__main__':
    # Brugge allow_unsafe_werkzeug=True kun til udvikling. Ikke i produktion!
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True, port=5000)