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

    playerPaddle.style.width = `${PADDLE_WIDTH}px`;
    playerPaddle.style.height = `${PADDLE_HEIGHT}px`;
    playerPaddle.style.bottom = '0px';

    gameBoard.style.width = `${GAME_WIDTH}px`;
    gameBoard.style.height = `${GAME_HEIGHT}px`;

    const ballTransitionStyle = `left ${GAME_LOOP_INTERVAL_MS / 1000}s linear, top ${GAME_LOOP_INTERVAL_MS / 1000}s linear`;
    const paddleTransitionStyle = `left ${GAME_LOOP_INTERVAL_MS / 1000}s linear`;

    socket.on('game_state', (data) => {
        ball.style.left = `${data.ball_x - (ball.offsetWidth / 2)}px`;
        ball.style.top = `${data.ball_y - (ball.offsetHeight / 2)}px`;
        playerPaddle.style.left = `${data.player_paddle_x}px`;
        scoreDisplay.textContent = data.score;

        if (data.game_over) {
            gameOverMessage.classList.remove('hidden');
        } else {
            gameOverMessage.classList.add('hidden');
        }

        if (data.game_over || !data.ball_moving) {
            ball.style.transition = 'none';
            playerPaddle.style.transition = 'none';
        } else {
            ball.style.transition = ballTransitionStyle;
            playerPaddle.style.transition = paddleTransitionStyle;
        }
    });

    // === NY KODE FOR BEDRE LONG-PRESS RESPONSIVITET ===
    let keysPressed = {}; // Objekt til at holde styr på, hvilke taster der er nede
    let paddleMoveInterval = null; // Til at gemme interval ID'et

    document.addEventListener('keydown', (e) => {
        // Forhindrer browser scrolling ved piletaster
        if (e.key === 'ArrowLeft' || e.key === 'ArrowRight' || e.key === ' ' || e.key === 'a' || e.key === 'd') {
            e.preventDefault();
        }

        // Tjek om tasten allerede er registreret som nede for at undgå gentagne keydown events fra OS'et
        if (keysPressed[e.key]) {
            return; // Tast er allerede nede, ignorer
        }
        keysPressed[e.key] = true; // Marker tasten som nede

        // Start eller genstart spillet med SPACE
        if (e.key === ' ') {
            socket.emit('start_game');
        }

        // Hvis en bevægelsestast er nede, start interval for at sende events
        if (e.key === 'ArrowLeft' || e.key === 'a') {
            if (!paddleMoveInterval) { // Kun start interval hvis det ikke allerede kører
                paddleMoveInterval = setInterval(() => {
                    if (keysPressed['ArrowLeft'] || keysPressed['a']) { // Tjek om tast stadig er nede
                        socket.emit('move_paddle', { direction: 'left' });
                    }
                }, 50); // Send 'move_paddle' event hvert 50ms (kan justeres)
            }
        } else if (e.key === 'ArrowRight' || e.key === 'd') {
            if (!paddleMoveInterval) { // Kun start interval hvis det ikke allerede kører
                paddleMoveInterval = setInterval(() => {
                    if (keysPressed['ArrowRight'] || keysPressed['d']) { // Tjek om tast stadig er nede
                        socket.emit('move_paddle', { direction: 'right' });
                    }
                }, 50); // Send 'move_paddle' event hvert 50ms (kan justeres)
            }
        }
    });

    document.addEventListener('keyup', (e) => {
        keysPressed[e.key] = false; // Marker tasten som oppe

        // Hvis ingen bevægelsestaster er nede, stop intervallet
        if (!(keysPressed['ArrowLeft'] || keysPressed['a'] || keysPressed['ArrowRight'] || keysPressed['d'])) {
            if (paddleMoveInterval) {
                clearInterval(paddleMoveInterval);
                paddleMoveInterval = null;
            }
        }
    });
});