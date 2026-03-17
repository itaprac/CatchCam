import "./styles.css";

import { OpenDayGame } from "./game.js";
import { getRank, loadLeaderboard, saveScore } from "./leaderboard.js";

const app = document.querySelector("#app");

app.innerHTML = `
  <div class="app-shell" id="app-shell">
    <header class="topbar">
      <button class="nav-link is-active" data-view="play">Graj</button>
      <button class="nav-link" data-view="leaderboard">Leaderboard</button>
    </header>

    <main class="views">
      <section class="view is-active" data-view-panel="play">
        <section class="stage-shell">
          <video id="camera" playsinline muted></video>
          <canvas id="game-canvas"></canvas>

          <div class="overlay-card" id="start-overlay">
            <h1>CatchCam</h1>
            <p class="overlay-copy">Wpisz imie i zacznij od razu. Kamera pokazuje tez wykrywanie rak i sylwetki.</p>
            <form id="player-form" class="player-form">
              <input
                id="player-name"
                name="player-name"
                maxlength="20"
                placeholder="Twoje imie"
                autocomplete="off"
                required
              />
              <button type="submit">Graj</button>
            </form>
          </div>

          <div class="overlay-card is-hidden" id="result-overlay">
            <p class="result-kicker">Twoj wynik</p>
            <h2 id="result-score">0 pkt</h2>
            <p id="result-player">Gracz</p>
            <ol class="result-board" id="result-board"></ol>
            <button id="play-again-button">Graj ponownie</button>
          </div>
        </section>
      </section>

      <section class="view" data-view-panel="leaderboard">
        <section class="board-shell">
          <h2>Leaderboard</h2>
          <ol id="leaderboard-list" class="leaderboard-list"></ol>
        </section>
      </section>
    </main>
  </div>
`;

const appShell = document.querySelector("#app-shell");
const navLinks = [...document.querySelectorAll(".nav-link")];
const panels = [...document.querySelectorAll("[data-view-panel]")];

const startOverlay = document.querySelector("#start-overlay");
const resultOverlay = document.querySelector("#result-overlay");
const playerForm = document.querySelector("#player-form");
const nameInput = document.querySelector("#player-name");
const playAgainButton = document.querySelector("#play-again-button");
const leaderboardList = document.querySelector("#leaderboard-list");
const resultBoard = document.querySelector("#result-board");
const resultScore = document.querySelector("#result-score");
const resultPlayer = document.querySelector("#result-player");

const game = new OpenDayGame({
  video: document.querySelector("#camera"),
  canvas: document.querySelector("#game-canvas"),
  onStateChange: handleStateChange,
  onResult: handleResult,
});

let leaderboardEntries = loadLeaderboard();
let lastPlayerName = "";

renderLeaderboard(leaderboardList, leaderboardEntries);
renderLeaderboard(resultBoard, leaderboardEntries, true);

boot();

for (const link of navLinks) {
  link.addEventListener("click", () => {
    if (appShell.classList.contains("is-playing")) {
      return;
    }
    setView(link.dataset.view);
  });
}

playerForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const playerName = nameInput.value.trim();
  if (!playerName) {
    nameInput.focus();
    return;
  }

  lastPlayerName = playerName;
  resultOverlay.classList.add("is-hidden");
  startOverlay.classList.add("is-hidden");
  setView("play");
  game.startRound(playerName);
});

playAgainButton.addEventListener("click", () => {
  resultOverlay.classList.add("is-hidden");
  startOverlay.classList.remove("is-hidden");
  nameInput.value = lastPlayerName;
  nameInput.focus();
});

window.addEventListener("resize", () => game.resizeCanvas());

async function boot() {
  try {
    await game.init();
    await game.startCamera();
    nameInput.focus();
  } catch (error) {
    startOverlay.classList.remove("is-hidden");
    startOverlay.innerHTML = `
      <h1>CatchCam</h1>
      <p class="error-copy">Nie udalo sie uruchomic kamery. Sprawdz uprawnienia przegladarki i odswiez strone.</p>
    `;
    console.error(error);
  }
}

function handleStateChange(state) {
  appShell.classList.toggle("is-playing", state.isPlaying);
}

function handleResult(result) {
  appShell.classList.remove("is-playing");
  leaderboardEntries = saveScore(result);
  renderLeaderboard(leaderboardList, leaderboardEntries);
  renderLeaderboard(resultBoard, leaderboardEntries, true);

  const rank = getRank(leaderboardEntries, result.score, result.combo);
  resultScore.textContent = `${result.score} pkt`;
  resultPlayer.textContent = `${result.name}${rank ? ` | miejsce #${rank}` : ""}`;
  resultOverlay.classList.remove("is-hidden");
}

function renderLeaderboard(target, entries, compact = false) {
  if (!entries.length) {
    target.innerHTML = `<li class="empty-state">Brak wynikow.</li>`;
    return;
  }

  const slice = compact ? entries.slice(0, 6) : entries;
  target.innerHTML = slice
    .map(
      (entry, index) => `
        <li>
          <span class="place">#${index + 1}</span>
          <span class="name">${escapeHtml(entry.name)}</span>
          <span class="score">${entry.score}</span>
        </li>
      `,
    )
    .join("");
}

function setView(view) {
  for (const item of navLinks) {
    item.classList.toggle("is-active", item.dataset.view === view);
  }
  for (const panel of panels) {
    panel.classList.toggle("is-active", panel.dataset.viewPanel === view);
  }
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
