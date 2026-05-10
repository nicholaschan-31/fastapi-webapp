const authMessage = document.querySelector("#authMessage");
const loginForm = document.querySelector("#loginForm");
const registerForm = document.querySelector("#registerForm");

function setMessage(text, isError = false) {
  authMessage.textContent = text;
  authMessage.classList.toggle("error", isError);
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Request failed");
  }

  return response.json();
}

async function login(username, password) {
  const body = new URLSearchParams();
  body.set("username", username);
  body.set("password", password);

  const data = await requestJson("/login/", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body,
  });

  localStorage.setItem("gameLibraryToken", data.access_token);
  window.location.href = "/";
}

if (localStorage.getItem("gameLibraryToken")) {
  window.location.href = "/";
}

if (loginForm) {
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(loginForm);

    try {
      await login(formData.get("username"), formData.get("password"));
    } catch (error) {
      setMessage(error.message, true);
    }
  });
}

if (registerForm) {
  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(registerForm);

    try {
      await requestJson("/register/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: formData.get("username"),
          email: formData.get("email"),
          password: formData.get("password"),
        }),
      });

      await login(formData.get("username"), formData.get("password"));
    } catch (error) {
      setMessage(error.message, true);
    }
  });
}
