document.addEventListener('DOMContentLoaded', () => {
    // Forbind til Socket.IO serveren
    const socket = io();
    
    // Hent DOM-elementer
    const ball = document.getElementById('ball');
    const playerPaddle = document.getElementById('player-paddle');
    const scoreDisplay = document.getElementById('score');
    const gameOverMessage = document.getElementById('game-over-message');
    // const startButton = document.getElementById('start-button'); // FJERNET
    const gameBoard = document.getElementById('game-board');

    const existingBricks = new Map();

    // Spilkonstanter (match med Python)
    const GAME_WIDTH = 800;
    const GAME_HEIGHT = 600;
    const PADDLE_HEIGHT = 15;
    const BALL_RADIUS = 10;
    const PADDLE_WIDTH = 100;
    const GAME_LOOP_INTERVAL_MS = 16;

    // Sæt initial størrelse på bolden (passer til BALL_RADIUS)
    ball.style.width = `${BALL_RADIUS * 2}px`;
    ball.style.height = `${BALL_RADIUS * 2}px`;

    // Sæt initial størrelse og position på paddle
    playerPaddle.style.width = `${PADDLE_WIDTH}px`;
    playerPaddle.style.height = `${PADDLE_HEIGHT}px`;
    playerPaddle.style.bottom = '0px';

    // Sæt størrelsen på game-board baseret på Flask variabler
    gameBoard.style.width = `${GAME_WIDTH}px`;
    gameBoard.style.height = `${GAME_HEIGHT}px`;

    // Definer CSS transition styles. Disse vil blive anvendt dynamisk.
    const ballTransitionStyle = `left ${GAME_LOOP_INTERVAL_MS / 1000}s linear, top ${GAME_LOOP_INTERVAL_MS / 1000}s linear`;
    const paddleTransitionStyle = `left ${GAME_LOOP_INTERVAL_MS / 1000}s linear`;


    // Lyt efter 'game_state' events fra serveren
    socket.on('game_state', (data) => {
        // Opdater boldens position
        ball.style.left = `${data.ball_x - (ball.offsetWidth / 2)}px`;
        ball.style.top = `${data.ball_y - (ball.offsetHeight / 2)}px`;

        // Opdater spillerens paddle position
        playerPaddle.style.left = `${data.player_paddle_x}px`;

        // Opdater score
        scoreDisplay.textContent = data.score;

        // Vis/skjul game over besked (nu centreret i spilbrættet)
        if (data.game_over) {
            gameOverMessage.classList.remove('hidden');
        } else {
            gameOverMessage.classList.add('hidden');
        }

        // === STARTKNAP LOGIK ER FJERNET HERFRA ===
        // Da startknappen er fjernet fra HTML, er denne logik ikke længere nødvendig.

        // Slå transitions fra/til baseret på spillets tilstand for at undgå ujævn animation
        if (data.game_over || !data.ball_moving) {
            ball.style.transition = 'none'; // Ingen transition når spillet er over eller bolden står stille
            playerPaddle.style.transition = 'none';
        } else {
            // Aktiver transitions, når spillet er i gang og bolden bevæger sig
            ball.style.transition = ballTransitionStyle;
            playerPaddle.style.transition = paddleTransitionStyle;
        }
        const brickIds = new Set();

        data.bricks.forEach((brick, index) => {
            const id = `brick-${index}`;
            brickIds.add(id);

        let brickElem = existingBricks.get(id);
        if (!brickElem) {
            brickElem = document.createElement('div');
            brickElem.id = id;
            brickElem.classList.add('brick');
            if (!brick.breakable) {
                brickElem.classList.add('unbreakable');
            }
            gameBoard.appendChild(brickElem);
            existingBricks.set(id, brickElem);
        }

        brickElem.style.left = `${brick.x}px`;
        brickElem.style.top = `${brick.y}px`;
        brickElem.style.width = `${brick.width}px`;
        brickElem.style.height = `${brick.height}px`;
    });

// Fjern bricks der ikke længere findes
    for (let [id, elem] of existingBricks.entries()) {
        if (!brickIds.has(id)) {
            elem.remove();
            existingBricks.delete(id);
        }
    }
    });

    // Lyt efter tastetryk for at flytte paddle eller starte spillet
    document.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowLeft' || e.key === 'a') {
            socket.emit('move_paddle', { direction: 'left' });
        } else if (e.key === 'ArrowRight' || e.key === 'd') {
            socket.emit('move_paddle', { direction: 'right' });
        } else if (e.key === ' ') { // Spacebar er nu den eneste måde at starte/genstarte på
            socket.emit('start_game');
        }
    });

});