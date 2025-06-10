document.addEventListener('DOMContentLoaded', () => {
    const socket = io();
    const ball = document.getElementById('ball');
    const playerPaddle = document.getElementById('player-paddle');
    const scoreDisplay = document.getElementById('score');
    const gameOverMessage = document.getElementById('game-over-message');
    const gameBoard = document.getElementById('game-board');

    const GAME_WIDTH = 800;
    const GAME_HEIGHT = 600;
    const PADDLE_HEIGHT = 15;
    const BALL_RADIUS = 10;
    const PADDLE_WIDTH = 100;
    const GAME_LOOP_INTERVAL_MS = 16;

    ball.style.width = `${BALL_RADIUS * 2}px`;
    ball.style.height = `${BALL_RADIUS * 2}px`;
    ball.style.zIndex = '10';
    playerPaddle.style.width = `${PADDLE_WIDTH}px`;
    playerPaddle.style.height = `${PADDLE_HEIGHT}px`;
    playerPaddle.style.bottom = '0px';
    gameBoard.style.width = `${GAME_WIDTH}px`;
    gameBoard.style.height = `${GAME_HEIGHT}px`;

    const ballTransitionStyle = `left ${GAME_LOOP_INTERVAL_MS / 1000}s linear, top ${GAME_LOOP_INTERVAL_MS / 1000}s linear`;
    const paddleTransitionStyle = `left ${GAME_LOOP_INTERVAL_MS / 1000}s linear`;

    const MAX_TRAIL_ELEMENTS = 10;
    const trailElements = [];
    const existingBricks = new Map();
    const brickIds = new Set();
    let keysPressed = {};
    let paddleMoveInterval = null;

    function createTrailElement(x, y, radius) {
        const trail = document.createElement('div');
        trail.classList.add('ball-trail');
        trail.style.width = `${radius * 2}px`;
        trail.style.height = `${radius * 2}px`;
        trail.style.left = `${x - radius}px`;
        trail.style.top = `${y - radius}px`;
        gameBoard.appendChild(trail);

        trailElements.push(trail);
        if (trailElements.length > MAX_TRAIL_ELEMENTS) {
            trailElements.shift().remove();
        }

        requestAnimationFrame(() => {
            trail.style.opacity = 0;
            trail.style.transform = 'scale(0.8)';
            setTimeout(() => trail.remove(), 500);
        });
    }

    socket.on('game_state', (data) => {
        if (data.ball_moving && data.score % 2 === 0) {
            createTrailElement(data.ball_x, data.ball_y, BALL_RADIUS);
        }

        ball.style.left = `${data.ball_x - (ball.offsetWidth / 2)}px`;
        ball.style.top = `${data.ball_y - (ball.offsetHeight / 2)}px`;
        playerPaddle.style.left = `${data.player_paddle_x}px`;
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

        if (data.game_over || !data.ball_moving) {
            ball.style.transition = 'none';
            playerPaddle.style.transition = 'none';
            trailElements.forEach(trail => trail.remove());
            trailElements.length = 0;
        } else {
            ball.style.transition = ballTransitionStyle;
            playerPaddle.style.transition = paddleTransitionStyle;
        }

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
