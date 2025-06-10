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
    // Initial z-index for bolden, så den er over sporet
    ball.style.zIndex = '10';

    playerPaddle.style.width = `${PADDLE_WIDTH}px`;
    playerPaddle.style.height = `${PADDLE_HEIGHT}px`;
    playerPaddle.style.bottom = '0px';

    gameBoard.style.width = `${GAME_WIDTH}px`;
    gameBoard.style.height = `${GAME_HEIGHT}px`;

    const ballTransitionStyle = `left ${GAME_LOOP_INTERVAL_MS / 1000}s linear, top ${GAME_LOOP_INTERVAL_MS / 1000}s linear`;
    const paddleTransitionStyle = `left ${GAME_LOOP_INTERVAL_MS / 1000}s linear`;

    let keysPressed = {};
    let paddleMoveInterval = null;

    // === NY KODE FOR BOLDSPOR (BALL TRAIL) ===
    const MAX_TRAIL_ELEMENTS = 10; // Antal spor-elementer
    const trailElements = []; // Array til at holde styr på spor-elementerne

    // Funktion til at oprette et nyt spor-element
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
            const oldTrail = trailElements.shift();
            oldTrail.remove();
        }

        // Ingen indledende opacity sætning i JS her, da det er defineret i CSS
        // og vi vil have det til at starte med 1 (eller den farve, du vælger i CSS)
        // og så lade transitionen styre fade-out.

        requestAnimationFrame(() => {
            // Nu skal opacity bare falme ud fra sin startværdi (som er 1 fra CSS)
            trail.style.opacity = 0; // Sæt opaciteten til 0 for at starte transitionen (fade out)
            trail.style.transform = 'scale(0.8)';
            setTimeout(() => {
                if (trail.parentNode) {
                    trail.remove();
                }
            }, 500);
        });
    }
    // === SLUT NY KODE TIL BOLDSPOR ===

    socket.on('game_state', (data) => {
        // === NY KODE TIL AT GENERERE SPOR ===
        // Opret et spor-element hvis bolden bevæger sig, og kun hver anden frame
        if (data.ball_moving && data.score % 2 === 0) { // Bruger score som en simpel hack til at begrænse, kan også bruge en tæller
            createTrailElement(data.ball_x, data.ball_y, BALL_RADIUS);
        }
        // === SLUT NY KODE TIL AT GENERERE SPOR ===

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
            // === NY KODE: RYDD OP I SPOR VED SPILLETS SLUT ===
            trailElements.forEach(trail => trail.remove());
            trailElements.length = 0; // Tøm arrayet
            // === SLUT NY KODE ===
        } else {
            ball.style.transition = ballTransitionStyle;
            playerPaddle.style.transition = paddleTransitionStyle;
        }
    });

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
        brickElem.classList.remove('unbreakable'); 
        if (!brick.breakable) {
            brickElem.classList.add('unbreakable');
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
        if (e.key === 'ArrowLeft' || e.key === 'ArrowRight' || e.key === ' ' || e.key === 'a' || e.key === 'd') {
            e.preventDefault();
        }

        if (keysPressed[e.key]) {
            return;
        }
        keysPressed[e.key] = true;

        if (e.key === ' ') {
            socket.emit('start_game');
        }

        if (e.key === 'ArrowLeft' || e.key === 'a') {
            if (!paddleMoveInterval) {
                paddleMoveInterval = setInterval(() => {
                    if (keysPressed['ArrowLeft'] || keysPressed['a']) {
                        socket.emit('move_paddle', { direction: 'left' });
                    }
                }, 50);
            }
        } else if (e.key === 'ArrowRight' || e.key === 'd') {
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
            if (paddleMoveInterval) {
                clearInterval(paddleMoveInterval);
                paddleMoveInterval = null;
            }
        }
    });
});