document.addEventListener('DOMContentLoaded', () => {
    // Forbind til Socket.IO serveren
    const socket = io();

    // Hent DOM-elementer
    const ball = document.getElementById('ball');
    const playerPaddle = document.getElementById('player-paddle');
    const scoreDisplay = document.getElementById('score');
    const gameOverMessage = document.getElementById('game-over-message');
    const startButton = document.getElementById('start-button');
    const gameBoard = document.getElementById('game-board');

    // Spilkonstanter (match med Python)
    const GAME_WIDTH = 800; // Skal matche Python
    const GAME_HEIGHT = 600; // Skal matche Python
    const PADDLE_HEIGHT = 15; // Skal matche Python

    // Initial position for paddle (bunden af skærmen)
    playerPaddle.style.bottom = '0px';

    // Lyt efter 'game_state' events fra serveren
    socket.on('game_state', (data) => {
        // Opdater boldens position
        ball.style.left = `${data.ball_x - (ball.offsetWidth / 2)}px`;
        ball.style.top = `${data.ball_y - (ball.offsetHeight / 2)}px`;

        // Opdater spillerens paddle position
        playerPaddle.style.left = `${data.player_paddle_x}px`;

        // Opdater score
        scoreDisplay.textContent = data.score;

        // Vis/skjul game over besked
        if (data.game_over) {
            gameOverMessage.classList.remove('hidden');
            startButton.textContent = 'Restart Game';
            startButton.classList.remove('hidden');
        } else {
            gameOverMessage.classList.add('hidden');
        }

        // Skjul startknappen hvis spillet er startet og ikke game over
        if (data.game_started && !data.game_over) {
            startButton.classList.add('hidden');
        }
    });

    // Lyt efter tastetryk for at flytte paddle
    document.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowLeft' || e.key === 'a') {
            socket.emit('move_paddle', { direction: 'left' });
        } else if (e.key === 'ArrowRight' || e.key === 'd') {
            socket.emit('move_paddle', { direction: 'right' });
        } else if (e.key === ' ' && gameOverMessage.classList.contains('hidden') === false) {
             // Tryk på SPACE når spillet er slut for at starte igen
            socket.emit('start_game');
        }
    });

    // Lyt efter klik på startknappen
    startButton.addEventListener('click', () => {
        socket.emit('start_game');
    });

    // Sæt initial størrelse på bolden (passer til BALL_RADIUS)
    const BALL_RADIUS = 10; // Match BALL_RADIUS i Python
    ball.style.width = `${BALL_RADIUS * 2}px`;
    ball.style.height = `${BALL_RADIUS * 2}px`;

    // Sæt initial størrelse og position på paddle
    const PADDLE_WIDTH = 100; // Match PADDLE_WIDTH i Python
    playerPaddle.style.width = `${PADDLE_WIDTH}px`;
    playerPaddle.style.height = `${PADDLE_HEIGHT}px`;
    playerPaddle.style.bottom = '0px'; // Altid i bunden

    // Sæt størrelsen på game-board baseret på Flask variabler
    gameBoard.style.width = `${GAME_WIDTH}px`;
    gameBoard.style.height = `${GAME_HEIGHT}px`;

});