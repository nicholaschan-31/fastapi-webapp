const state = {
  token: localStorage.getItem("gameLibraryToken"),
  user: null,
  games: [],
};

const gameForm = document.querySelector("#gameForm");
const logoutButton = document.querySelector("#logoutButton");
const appMessage = document.querySelector("#appMessage");
const playerName = document.querySelector("#playerName");
const playerCard = document.querySelector("#playerCard");
const libraryGrid = document.querySelector("#libraryGrid");
const stats = document.querySelector("#stats");
const deleteModal = document.querySelector("#deleteModal");
const deleteGameTitle = document.querySelector("#deleteGameTitle");
const cancelDeleteButton = document.querySelector("#cancelDeleteButton");
const confirmDeleteButton = document.querySelector("#confirmDeleteButton");
let pendingDeleteResolver = null;

function setMessage(text, isError = false) {
  appMessage.textContent = text;
  appMessage.classList.toggle("error", isError);
}

async function apiFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.token) {
    headers.set("Authorization", `Bearer ${state.token}`);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Request failed");
  }

  return response.json();
}

function jsonHeaders() {
  return {
    "Content-Type": "application/json",
  };
}

async function loadSession() {
  if (!state.token) {
    window.location.href = "/login/";
    return;
  }

  try {
    state.user = await apiFetch("/users/me/");
    state.games = await apiFetch("/games/");
    renderApp();
  } catch (error) {
    state.token = null;
    state.user = null;
    state.games = [];
    localStorage.removeItem("gameLibraryToken");
    window.location.href = "/login/";
  }
}

function renderApp() {
  playerName.textContent = state.user.username;
  playerCard.querySelector(".label").textContent = "SIGNED IN";
  renderGames(state.games);
}

function renderStats(games) {
  const counts = games.reduce((total, game) => {
    total[game.status] += 1;
    return total;
  }, { playing: 0, completed: 0, dropped: 0 });

  stats.innerHTML = `
    <span>${counts.playing} Playing</span>
    <span>${counts.completed} Completed</span>
    <span>${counts.dropped} Dropped</span>
  `;
}

function renderGames(games) {
  renderStats(games);

  if (!games.length) {
    libraryGrid.innerHTML = `
      <article class="empty-state">
        <div class="mini-console" aria-hidden="true"></div>
        <h3>No games loaded</h3>
        <p>Add your first game to begin tracking your backlog.</p>
      </article>
    `;
    return;
  }

  libraryGrid.innerHTML = games.map((game) => `
    <article class="game-card">
      <h3>${escapeHtml(game.title)}</h3>
      <div class="meta">
        <span class="badge">${escapeHtml(game.status.toUpperCase())}</span>
        <span>Platform: ${escapeHtml(game.platform || "Unknown")}</span>
        <span>Genre: ${escapeHtml(game.genre || "Unknown")}</span>
        <span>Year: ${game.release_year || "Unknown"}</span>
      </div>
      <div class="status-row">
        ${statusButton(game, "playing", "Play")}
        ${statusButton(game, "completed", "Done")}
        ${statusButton(game, "dropped", "Drop")}
      </div>
      <button class="delete-button" type="button" data-delete-id="${game.id}">
        Delete Game
      </button>
    </article>
  `).join("");

  document.querySelectorAll("[data-status-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      await updateStatus(button.dataset.statusId, button.dataset.status);
    });
  });

  document.querySelectorAll("[data-delete-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      await deleteGame(button.dataset.deleteId);
    });
  });
}

function statusButton(game, status, label) {
  const active = game.status === status ? " active" : "";
  return `
    <button class="status-button${active}" type="button" data-status-id="${game.id}" data-status="${status}">
      ${label}
    </button>
  `;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function updateStatus(gameId, nextStatus) {
  try {
    const updatedGame = await apiFetch(`/games/${gameId}/status`, {
      method: "PUT",
      headers: jsonHeaders(),
      body: JSON.stringify({ status: nextStatus }),
    });

    state.games = state.games.map((game) => (
      game.id === updatedGame.id ? updatedGame : game
    ));
    renderGames(state.games);
  } catch (error) {
    setMessage(error.message, true);
  }
}

async function deleteGame(gameId) {
  const selectedGame = state.games.find((game) => game.id === Number(gameId));
  const gameTitle = selectedGame ? selectedGame.title : "Selected game";
  const shouldDelete = await askDeleteConfirmation(gameTitle);
  if (!shouldDelete) {
    return;
  }

  try {
    await apiFetch(`/games/${gameId}`, {
      method: "DELETE",
    });

    state.games = state.games.filter((game) => game.id !== Number(gameId));
    renderGames(state.games);
    setMessage("Game deleted.");
  } catch (error) {
    setMessage(error.message, true);
  }
}

function askDeleteConfirmation(gameTitle) {
  deleteGameTitle.textContent = gameTitle;
  deleteModal.classList.remove("hidden");
  confirmDeleteButton.focus();

  return new Promise((resolve) => {
    pendingDeleteResolver = resolve;
  });
}

function closeDeleteModal(confirmed) {
  deleteModal.classList.add("hidden");

  if (pendingDeleteResolver) {
    pendingDeleteResolver(confirmed);
    pendingDeleteResolver = null;
  }
}

gameForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const formData = new FormData(gameForm);
  const releaseYear = formData.get("release_year");

  try {
    const game = await apiFetch("/games/", {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify({
        title: formData.get("title"),
        platform: formData.get("platform") || null,
        genre: formData.get("genre") || null,
        release_year: releaseYear ? Number(releaseYear) : null,
        status: formData.get("status"),
      }),
    });

    state.games = [game, ...state.games];
    gameForm.reset();
    renderGames(state.games);
    setMessage("Game added.");
  } catch (error) {
    setMessage(error.message, true);
  }
});

logoutButton.addEventListener("click", () => {
  state.token = null;
  state.user = null;
  state.games = [];
  localStorage.removeItem("gameLibraryToken");
  window.location.href = "/login/";
});

confirmDeleteButton.addEventListener("click", () => {
  closeDeleteModal(true);
});

cancelDeleteButton.addEventListener("click", () => {
  closeDeleteModal(false);
});

deleteModal.addEventListener("click", (event) => {
  if (event.target === deleteModal) {
    closeDeleteModal(false);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !deleteModal.classList.contains("hidden")) {
    closeDeleteModal(false);
  }
});

loadSession();
