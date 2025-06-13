document.addEventListener('DOMContentLoaded', () => {
    const socket = io();
    const playerPaddle = document.getElementById('player-paddle');
    const scoreDisplay = document.getElementById('score');
    const gameOverMessage = document.getElementById('game-over-message');
    const gameBoard = document.getElementById('game-board');
    const powerUpContainer = document.getElementById('power-up-container'); 

    const GAME_WIDTH = 800;
    const GAME_HEIGHT = 600;
    const PADDLE_HEIGHT = 15; 
    const BALL_RADIUS = 10;
    const PADDLE_WIDTH_BASE = 100; 
    const GAME_LOOP_INTERVAL_MS = 16;
    const POWER_UP_RADIUS = 15; 

    playerPaddle.style.width = `${PADDLE_WIDTH_BASE}px`; 
    playerPaddle.style.height = `${PADDLE_HEIGHT}px`;
    playerPaddle.style.bottom = '0px';
    
    gameBoard.style.width = `${GAME_WIDTH}px`;
    gameBoard.style.height = `${GAME_HEIGHT}px`;

    const ballTransitionStyle = `left ${GAME_LOOP_INTERVAL_MS / 1000}s linear, top ${GAME_LOOP_INTERVAL_MS / 1000}s linear`;
    const paddleTransitionStyle = `left ${GAME_LOOP_INTERVAL_MS / 1000}s linear, width ${GAME_LOOP_INTERVAL_MS / 1000}s linear`; 

    const existingBricks = new Map();
    const brickIds = new Set();
    const existingFallingItems = new Map(); 
    const fallingItemIds = new Set(); 
    const existingBalls = new Map(); 
    const ballIds = new Set(); 

    let keysPressed = {};
    let paddleMoveInterval = null;

    socket.on('game_state', (data) => {
        playerPaddle.style.left = `${data.player_paddle_x}px`;
        playerPaddle.style.width = `${data.player_paddle_width}px`;

        scoreDisplay.textContent = data.score;

        if (data.game_over) {
            gameOverMessage.classList.remove('hidden');
            gameOverMessage.textContent = 'Game Over! Press SPACE to restart.';
        } else if (!data.game_started) {
            gameOverMessage.classList.remove('hidden');
            gameOverMessage.textContent = 'Press SPACE to start';
        } else {
            gameOverMessage.classList.add('hidden');
        }

        // --- Ball rendering logic (Multi-ball) ---
        ballIds.clear();
        data.balls.forEach(ball_data => {
            ballIds.add(ball_data.id);

            let ballElem = existingBalls.get(ball_data.id);
            if (!ballElem) {
                console.log(`Creating new ball element for ID: ${ball_data.id}, type: ${ball_data.type}`); // Log ved oprettelse
                ballElem = document.createElement('div');
                ballElem.id = `ball-${ball_data.id}`; 
                ballElem.classList.add('ball'); // All balls get 'ball' class
                ballElem.style.width = `${BALL_RADIUS * 2}px`;
                ballElem.style.height = `${BALL_RADIUS * 2}px`;
                ballElem.style.zIndex = '10'; 
                gameBoard.appendChild(ballElem);
                existingBalls.set(ball_data.id, ballElem);
            }

            // Dette er den vigtigste del at debugge
            ballElem.classList.toggle('normal', ball_data.type === 'normal');
            ballElem.classList.toggle('multi', ball_data.type === 'multi'); 

            // Log efter klasser er toggled
            console.log(`Updating ball ID: ${ball_data.id}, data.type: "${ball_data.type}", current classes: "${ballElem.className}"`);

            ballElem.style.left = `${ball_data.x - BALL_RADIUS}px`; 
            ballElem.style.top = `${ball_data.y - BALL_RADIUS}px`; 

            if (!ball_data.is_moving || data.game_over) {
                ballElem.style.transition = 'none';
            } else {
                ballElem.style.transition = ballTransitionStyle;
            }
        });

        for (let [id, elem] of existingBalls.entries()) {
            if (!ballIds.has(id)) {
                console.log(`Removing ball element for ID: ${id}`); // Log ved fjernelse
                elem.remove();
                existingBalls.delete(id);
            }
        }
        // --- End Ball rendering logic ---


        if (data.game_over || !data.game_started) { 
            playerPaddle.style.transition = 'none';
        } else {
            playerPaddle.style.transition = paddleTransitionStyle;
        }


        // Update bricks (unchanged)
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

        // --- Falling Item (Power-up/Debuff) rendering logic (unchanged) ---
        fallingItemIds.clear();
        data.falling_items.forEach(item => { 
            fallingItemIds.add(item.id);

            let itemElem = existingFallingItems.get(item.id);
            if (!itemElem) {
                itemElem = document.createElement('div');
                itemElem.id = item.id;
                itemElem.classList.add('power-up'); 
                itemElem.classList.add(item.type); 
                itemElem.style.width = `${POWER_UP_RADIUS * 2}px`;
                itemElem.style.height = `${POWER_UP_RADIUS * 2}px`;
                powerUpContainer.appendChild(itemElem); 
                existingFallingItems.set(item.id, itemElem);
            }
            itemElem.style.left = `${item.x}px`;
            itemElem.style.top = `${item.y}px`;
            itemElem.style.transition = `top ${GAME_LOOP_INTERVAL_MS / 1000}s linear`; 
        });

        for (let [id, elem] of existingFallingItems.entries()) {
            if (!fallingItemIds.has(id)) {
                elem.remove();
                existingFallingItems.delete(id);
            }
        }
        // --- End Falling Item rendering logic ---
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