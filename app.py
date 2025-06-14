import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import time
import threading
import random
import uuid # For unique IDs for power-ups

app = Flask(__name__)
socketio = SocketIO(app)

GAME_WIDTH = 800
GAME_HEIGHT = 600
PADDLE_WIDTH = 100
PADDLE_HEIGHT = 15
BALL_RADIUS = 10
GAME_LOOP_INTERVAL_MS = 16
BALL_SPEED_BASE = 5


POWER_UP_FALL_SPEED = 2
POWER_UP_RADIUS = 15 
PADDLE_ENLARGE_DURATION_SECONDS = 20
PADDLE_ENLARGE_FACTOR = 1.5
BALL_SLOW_DURATION_SECONDS = 10
BALL_SLOW_FACTOR = 0.5
BALL_FAST_DURATION_SECONDS = 10
BALL_FAST_FACTOR = 1.8
MULTI_BALL_COUNT = 2

class Game:
    def __init__(self):
        self.levels = self.load_levels()
        self.level_index = 0
        self.reset_game()
        self._game_loop_thread = None
        self.falling_items = [] 
        self.active_effects = {} 

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
        self.current_paddle_width = PADDLE_WIDTH 
        
        self.balls = [] 
        self.create_new_ball(ball_type='normal')

        self.current_ball_speed = BALL_SPEED_BASE 
        self.score = 0
        self.game_over = False
        self.game_started = False
        self.any_ball_moving = False 

        self.falling_items = [] 
        self.active_effects = {} 

        difficulty = self.level_index
        cols = 14
        spacing_x = 1
        start_x = 1
        brick_width = int((GAME_WIDTH - start_x - spacing_x * (cols - 1)) / cols)
        self.bricks = self.generate_brick_grid(6, cols, start_x, 0, brick_width, 20, spacing_x, 1, lambda r, c: self.random_brick_pattern(r, c, difficulty))

    def create_new_ball(self, x=None, y=None, dx=None, dy=None, ball_type='normal'):
        """Creates and adds a new ball to the game."""
        new_ball_x = x if x is not None else (self.player_paddle_x + (self.current_paddle_width // 2))
        new_ball_y = y if y is not None else (GAME_HEIGHT - PADDLE_HEIGHT - BALL_RADIUS - 1)
        new_ball_dx = dx if dx is not None else (random.choice([-1, 1]) * (BALL_SPEED_BASE // 2 + random.randint(0,2))) 
        new_ball_dy = dy if dy is not None else -BALL_SPEED_BASE

        self.balls.append({
            'id': str(uuid.uuid4()), 
            'x': new_ball_x,
            'y': new_ball_y,
            'dx': new_ball_dx,
            'dy': new_ball_dy,
            'is_moving': False,
            'type': ball_type 
        })

    def get_game_state(self):
        return {
            'balls': self.balls, 
            'player_paddle_x': self.player_paddle_x,
            'player_paddle_width': self.current_paddle_width, 
            'score': self.score,
            'game_over': self.game_over,
            'game_started': self.game_started,
            'bricks': self.bricks,
            'falling_items': self.falling_items 
        }

    def update_game_state(self):
        self.check_active_effects() 

        if self.game_over or not self.game_started:
            return
        
        if not self.any_ball_moving and self.game_started:
            for ball in self.balls:
                ball['x'] = self.player_paddle_x + (self.current_paddle_width // 2)
                ball['y'] = GAME_HEIGHT - PADDLE_HEIGHT - BALL_RADIUS - 1
            return 

        self.move_balls_with_collisions() 
        self.move_falling_items() 
        self.check_falling_item_collisions()

        if all(not b['breakable'] for b in self.bricks):
            self.level_index = (self.level_index + 1) % len(self.levels)
            self.reset_game()
            self.game_started = False
            self.any_ball_moving = False 

    def move_balls_with_collisions(self): 
        balls_to_keep = []
        
        for ball in list(self.balls): 
            if not ball['is_moving']:
                balls_to_keep.append(ball)
                continue 

            effective_speed_x = abs(ball['dx']) * self.current_ball_speed / BALL_SPEED_BASE
            effective_speed_y = abs(ball['dy']) * self.current_ball_speed / BALL_SPEED_BASE

            steps = int(max(effective_speed_x, effective_speed_y)) + 1 
            if steps == 0: 
                balls_to_keep.append(ball)
                continue

            dx_step = ball['dx'] / steps * (self.current_ball_speed / BALL_SPEED_BASE)
            dy_step = ball['dy'] / steps * (self.current_ball_speed / BALL_SPEED_BASE)

            collision_this_ball_this_frame = False 

            for _ in range(steps):
                if collision_this_ball_this_frame: break 

                ball['x'] += dx_step
                ball['y'] += dy_step

                # Wall collisions
                if ball['x'] - BALL_RADIUS < 0:
                    ball['x'] = BALL_RADIUS
                    ball['dx'] *= -1
                    collision_this_ball_this_frame = True
                elif ball['x'] + BALL_RADIUS > GAME_WIDTH:
                    ball['x'] = GAME_WIDTH - BALL_RADIUS
                    ball['dx'] *= -1
                    collision_this_ball_this_frame = True
                
                if ball['y'] - BALL_RADIUS < 0:
                    ball['y'] = BALL_RADIUS
                    ball['dy'] *= -1
                    collision_this_ball_this_frame = True

                # Paddle collision
                if (ball['dy'] > 0 and 
                    ball['y'] + BALL_RADIUS >= GAME_HEIGHT - PADDLE_HEIGHT and 
                    ball['y'] + BALL_RADIUS <= GAME_HEIGHT - PADDLE_HEIGHT + abs(dy_step) + 1 and 
                    ball['x'] + BALL_RADIUS > self.player_paddle_x and 
                    ball['x'] - BALL_RADIUS < self.player_paddle_x + self.current_paddle_width):
                    
                    ball['y'] = GAME_HEIGHT - PADDLE_HEIGHT - BALL_RADIUS 
                    ball_center_x_on_paddle = ball['x'] - self.player_paddle_x - (self.current_paddle_width / 2)
                    normalized_impact = ball_center_x_on_paddle / (self.current_paddle_width / 2)
                    deflection_factor = 3.0
                    ball['dx'] = normalized_impact * deflection_factor
                    if abs(ball['dx']) < 1:
                        ball['dx'] = 1 if normalized_impact >= 0 else -1
                    ball['dy'] *= -1
                    self.score += 1
                    collision_this_ball_this_frame = True

            if ball['y'] + BALL_RADIUS > GAME_HEIGHT:
                print(f"Ball {ball['id']} lost.")
            else:
                balls_to_keep.append(ball)

        self.balls = balls_to_keep 

        if 'multi_ball' in self.active_effects:
            multi_balls_remaining = sum(1 for ball in self.balls if ball.get('type') == 'multi')
            if multi_balls_remaining == 0:
                print("Multi-ball effect ended because all multi-balls were lost.")
                del self.active_effects['multi_ball']

        if not self.balls and self.game_started:
            self.game_over = True
            self.game_started = False
            self.any_ball_moving = False 
            if 'multi_ball' in self.active_effects:
                del self.active_effects['multi_ball']


        bricks_after_collisions = [] 
        for brick in list(self.bricks): 
            brick_removed_this_frame = False 
            for ball in self.balls: 
                if self.check_collision_with_brick(brick, ball): 
                    if brick['breakable']:
                        self.score += 5
                        self.spawn_falling_item(brick['x'] + brick['width'] / 2, brick['y'] + brick['height'] / 2)
                        brick_removed_this_frame = True 
                    
                    overlap_x = (BALL_RADIUS + brick['width'] / 2) - abs(ball['x'] - (brick['x'] + brick['width'] / 2))
                    overlap_y = (BALL_RADIUS + brick['height'] / 2) - abs(ball['y'] - (brick['y'] + brick['height'] / 2))

                    if overlap_x > 0 and overlap_y > 0:
                        if overlap_x < overlap_y: 
                            ball['dx'] *= -1
                            if ball['x'] < brick['x'] + brick['width'] / 2: 
                                ball['x'] = brick['x'] - BALL_RADIUS
                            else:
                                ball['x'] = brick['x'] + brick['width'] + BALL_RADIUS
                        else: 
                            ball['dy'] *= -1
                            if ball['y'] < brick['y'] + brick['height'] / 2:
                                ball['y'] = brick['y'] - BALL_RADIUS
                            else:
                                ball['y'] = brick['y'] + brick['height'] + BALL_RADIUS
                    
                    if brick_removed_this_frame:
                        break 
            
            if not brick_removed_this_frame: 
                bricks_after_collisions.append(brick)

        self.bricks = bricks_after_collisions 

    def check_collision_with_brick(self, brick, ball_obj): 
        ball_center_x = ball_obj['x']
        ball_center_y = ball_obj['y']
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

        if not self.any_ball_moving and self.balls:
            old_paddle_x = self.player_paddle_x
            if direction == 'left':
                self.player_paddle_x = max(0, self.player_paddle_x - PADDLE_MOVE_AMOUNT)
            elif direction == 'right':
                self.player_paddle_x = min(GAME_WIDTH - self.current_paddle_width, self.player_paddle_x + PADDLE_MOVE_AMOUNT)
            
            paddle_dx = self.player_paddle_x - old_paddle_x
            if self.balls:
                self.balls[0]['x'] += paddle_dx
        else: 
            if direction == 'left':
                self.player_paddle_x = max(0, self.player_paddle_x - PADDLE_MOVE_AMOUNT)
            elif direction == 'right':
                self.player_paddle_x = min(GAME_WIDTH - self.current_paddle_width, self.player_paddle_x + PADDLE_MOVE_AMOUNT)


    def spawn_falling_item(self, x, y):
        if random.random() < 0.4: 
            item_type = random.choice(['slow_ball', 'enlarge_paddle', 'fast_ball', 'multi_ball']) 
            self.falling_items.append({
                'id': str(uuid.uuid4()), 
                'type': item_type,
                'x': x - POWER_UP_RADIUS, 
                'y': y - POWER_UP_RADIUS,
                'radius': POWER_UP_RADIUS
            })

    def move_falling_items(self):
        for item in self.falling_items:
            item['y'] += POWER_UP_FALL_SPEED
        self.falling_items = [item for item in self.falling_items if item['y'] < GAME_HEIGHT]

    def check_falling_item_collisions(self):
        collected_items = []
        for item in self.falling_items:
            if (item['y'] + item['radius'] > GAME_HEIGHT - PADDLE_HEIGHT and
                item['y'] - item['radius'] < GAME_HEIGHT and
                item['x'] + item['radius'] > self.player_paddle_x and
                item['x'] - item['radius'] < self.player_paddle_x + self.current_paddle_width):

                collected_items.append(item)
                self.apply_effect(item) 

        self.falling_items = [item for item in self.falling_items if item not in collected_items]

    def apply_effect(self, item): 
        current_time = time.time()
        if item['type'] == 'slow_ball':
            print("Applying slow_ball power-up!")
            self.current_ball_speed = BALL_SPEED_BASE * BALL_SLOW_FACTOR
            self.active_effects['slow_ball'] = current_time + BALL_SLOW_DURATION_SECONDS
        elif item['type'] == 'enlarge_paddle':
            print("Applying enlarge_paddle power-up!")
            self.current_paddle_width = PADDLE_WIDTH * PADDLE_ENLARGE_FACTOR

            self.player_paddle_x = min(GAME_WIDTH - self.current_paddle_width, self.player_paddle_x)
            self.active_effects['enlarge_paddle'] = current_time + PADDLE_ENLARGE_DURATION_SECONDS
        elif item['type'] == 'fast_ball': 
            print("Applying fast_ball de-buff!")
            self.current_ball_speed = BALL_SPEED_BASE * BALL_FAST_FACTOR
            self.active_effects['fast_ball'] = current_time + BALL_FAST_DURATION_SECONDS
        elif item['type'] == 'multi_ball': 
            print("Applying multi_ball effect: Spawning more balls!")

            current_balls_at_effect_time = list(self.balls)

            for existing_ball in current_balls_at_effect_time:
                for i in range(MULTI_BALL_COUNT):

                    new_dx = random.choice([-1, 1]) * (BALL_SPEED_BASE // 2 + random.randint(0,2))
                    new_dy = -BALL_SPEED_BASE

                    offset_x = (i - MULTI_BALL_COUNT // 2) * (BALL_RADIUS * 2 + 5) 
                    self.create_new_ball(
                        existing_ball['x'] + offset_x,
                        existing_ball['y'],
                        new_dx,
                        new_dy,
                        ball_type='multi'
                    )
                    
                    if self.game_started and self.any_ball_moving:
                        self.balls[-1]['is_moving'] = True 
            

            self.active_effects['multi_ball'] = True


    def check_active_effects(self): 
        current_time = time.time()
        expired_effects = []
        for effect_type, end_time in list(self.active_effects.items()): 
            if effect_type == 'multi_ball':
                
                continue 

            if current_time >= end_time:
                expired_effects.append(effect_type)

        for effect_type in expired_effects:
            print(f"Effect {effect_type} expired.")
            if effect_type == 'enlarge_paddle':
                self.current_paddle_width = PADDLE_WIDTH
            

            if effect_type in self.active_effects:
                del self.active_effects[effect_type]

        old_ball_speed = self.current_ball_speed


        if 'fast_ball' in self.active_effects:
            self.current_ball_speed = BALL_SPEED_BASE * BALL_FAST_FACTOR
            if old_ball_speed != self.current_ball_speed: 
                print(f"Ball speed set to FAST: {self.current_ball_speed}")
        elif 'slow_ball' in self.active_effects:
            self.current_ball_speed = BALL_SPEED_BASE * BALL_SLOW_FACTOR
            if old_ball_speed != self.current_ball_speed: 
                print(f"Ball speed set to SLOW: {self.current_ball_speed}")
        else:
            self.current_ball_speed = BALL_SPEED_BASE
            if old_ball_speed != self.current_ball_speed: 
                print(f"Ball speed reset to BASE: {self.current_ball_speed}")

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
        
        for ball in game.balls:
            ball['is_moving'] = True
            if ball['dx'] == 0 and ball['dy'] == 0:
                ball['dx'] = (game.current_ball_speed // 2) if ball['x'] < GAME_WIDTH // 2 else -(game.current_ball_speed // 2)
                ball['dy'] = -game.current_ball_speed

        game.game_started = True
        game.any_ball_moving = True 
        game.start_game_loop()
        emit('game_state', game.get_game_state())

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True, port=5000, use_reloader=False)
