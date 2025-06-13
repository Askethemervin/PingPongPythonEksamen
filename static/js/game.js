document.addEventListener('DOMContentLoaded', () => {
    const socket = io();
    const ball = document.getElementById('ball');
    const playerPaddle = document.getElementById('player-paddle');
    const scoreDisplay = document.getElementById('score');
    const gameOverMessage = document.getElementById('game-over-message');
    const gameBoard = document.getElementById('game-board');
    const powerUpContainer = document.getElementById('power-up-container'); // New: Get power-up container

    const GAME_WIDTH = 800;
    const GAME_HEIGHT = 600;
    // PADDLE_HEIGHT is used for paddle positioning, not necessarily its visual height if image is different
    const PADDLE_HEIGHT = 15; // Still used for vertical positioning in the game engine
    const BALL_RADIUS = 10;
    const PADDLE_WIDTH_BASE = 100; // Base paddle width
    const GAME_LOOP_INTERVAL_MS = 16;
    const POWER_UP_RADIUS = 15; // Match this with POWER_UP_RADIUS in app.py

    ball.style.width = `${BALL_RADIUS * 2}px`;
    ball.style.height = `${BALL_RADIUS * 2}px`;
    ball.style.zIndex = '10';
    
    // Initial paddle width (will be updated by game_state)
    playerPaddle.style.width = `${PADDLE_WIDTH_BASE}px`; 
    playerPaddle.style.height = `${PADDLE_HEIGHT}px`;
    playerPaddle.style.bottom = '0px';
    
    gameBoard.style.width = `${GAME_WIDTH}px`;
    gameBoard.style.height = `${GAME_HEIGHT}px`;

    const ballTransitionStyle = `left ${GAME_LOOP_INTERVAL_MS / 1000}s linear, top ${GAME_LOOP_INTERVAL_MS / 1000}s linear`;
    const paddleTransitionStyle = `left ${GAME_LOOP_INTERVAL_MS / 1000}s linear, width ${GAME_LOOP_INTERVAL_MS / 1000}s linear`; // Added width transition

    const existingBricks = new Map();
    const brickIds = new Set();
    const existingPowerUps = new Map(); // New: Map to track existing power-up elements
    const powerUpIds = new Set(); // New: Set to track active power-up IDs

    let keysPressed = {};
    let paddleMoveInterval = null;

    socket.on('game_state', (data) => {
        // Update ball and paddle
        ball.style.left = `${data.ball_x - (ball.offsetWidth / 2)}px`;
        ball.style.top = `${data.ball_y - (ball.offsetHeight / 2)}px`;
        playerPaddle.style.left = `${data.player_paddle_x}px`;
        
        // Update paddle width based on server state
        playerPaddle.style.width = `${data.player_paddle_width}px`;

        scoreDisplay.textContent = data.score;

        // Update game messages
        if (data.game_over) {
            gameOverMessage.classList.remove('hidden');
            gameOverMessage.textContent = 'Game Over! Press SPACE to restart.';
        } else if (!data.game_started) {
            gameOverMessage.classList.remove('hidden');
            gameOverMessage.textContent = 'Press SPACE to start';
        } else {
            gameOverMessage.classList.add('hidden');
        }

        // Apply transitions based on game state
        if (data.game_over || !data.ball_moving) {
            ball.style.transition = 'none';
            playerPaddle.style.transition = 'none';
        } else {
            ball.style.transition = ballTransitionStyle;
            playerPaddle.style.transition = paddleTransitionStyle;
        }

        // Update bricks
        brickIds.clear();
        data.bricks.forEach((brick, index) => {
            const id = `brick-${index}`;
            brickIds.add(id);

            let brickElem = existingBricks.get(id);
            if (!brickElem) {
                brickElem = document.createElement('div');
                brickElem.id = id;
                brickElem.classList.add('brick');
                gameBoard.appendChild(brickElem);
                existingBricks.set(id, brickElem);
            }

            brickElem.classList.toggle('unbreakable', !brick.breakable);
            brickElem.style.left = `${brick.x}px`;
            brickElem.style.top = `${brick.y}px`;
            brickElem.style.width = `${brick.width}px`;
            brickElem.style.height = `${brick.height}px`;
        });

        for (let [id, elem] of existingBricks.entries()) {
            if (!brickIds.has(id)) {
                elem.remove();
                existingBricks.delete(id);
            }
        }

        // --- Power-up rendering logic ---
        powerUpIds.clear();
        data.power_ups.forEach(pu => {
            powerUpIds.add(pu.id);

            let powerUpElem = existingPowerUps.get(pu.id);
            if (!powerUpElem) {
                powerUpElem = document.createElement('div');
                powerUpElem.id = pu.id;
                powerUpElem.classList.add('power-up');
                powerUpElem.classList.add(pu.type); // Add class for specific power-up type (e.g., 'slow_ball')
                powerUpElem.style.width = `${POWER_UP_RADIUS * 2}px`;
                powerUpElem.style.height = `${POWER_UP_RADIUS * 2}px`;
                powerUpContainer.appendChild(powerUpElem); // Append to the new container
                existingPowerUps.set(pu.id, powerUpElem);
            }
            powerUpElem.style.left = `${pu.x}px`;
            powerUpElem.style.top = `${pu.y}px`;
            powerUpElem.style.transition = `top ${GAME_LOOP_INTERVAL_MS / 1000}s linear`; // Smooth falling animation
        });

        // Remove power-up elements that no longer exist in the game state
        for (let [id, elem] of existingPowerUps.entries()) {
            if (!powerUpIds.has(id)) {
                elem.remove();
                existingPowerUps.delete(id);
            }
        }
        // --- End Power-up rendering logic ---
    });

    document.addEventListener('keydown', (e) => {
        if (["ArrowLeft", "ArrowRight", " ", "a", "d"].includes(e.key)) {
            e.preventDefault();
        }
        if (keysPressed[e.key]) return;
        keysPressed[e.key] = true;

        if (e.key === ' ') socket.emit('start_game');

        if (["ArrowLeft", "a"].includes(e.key)) {
            if (!paddleMoveInterval) {
                paddleMoveInterval = setInterval(() => {
                    if (keysPressed['ArrowLeft'] || keysPressed['a']) {
                        socket.emit('move_paddle', { direction: 'left' });
                    }
                }, 50);
            }
        } else if (["ArrowRight", "d"].includes(e.key)) {
            if (!paddleMoveInterval) {
                paddleMoveInterval = setInterval(() => {
                    if (keysPressed['ArrowRight'] || keysPressed['d']) {
                        socket.emit('move_paddle', { direction: 'right' });
                    }
                }, 50);
            }
        }
    });

    document.addEventListener('keyup', (e) => {
        keysPressed[e.key] = false;
        if (!(keysPressed['ArrowLeft'] || keysPressed['a'] || keysPressed['ArrowRight'] || keysPressed['d'])) {
            clearInterval(paddleMoveInterval);
            paddleMoveInterval = null;
        }
    });
});