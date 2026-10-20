const log = document.getElementById("log");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const history = [];

function addMsg(text, cls) {
  const el = document.createElement("div");
  el.className = "msg " + cls;
  el.textContent = text;
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
  return el;
}

async function send(text) {
  text = text.trim();
  if (!text) return;
  addMsg(text, "user");
  history.push({ role: "user", content: text });
  input.value = "";
  input.style.height = "auto";
  sendBtn.disabled = true;

  const typing = addMsg("", "bot");
  typing.innerHTML = '<span class="typing"><i></i><i></i><i></i></span>';

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history }),
    });
    const data = await res.json();
    typing.remove();
    if (!res.ok) throw new Error(data.error || "Something went wrong.");
    addMsg(data.reply, "bot");
    history.push({ role: "assistant", content: data.reply });
  } catch (err) {
    typing.remove();
    addMsg(err.message, "bot error");
    history.pop(); // let the user retry the same message
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

sendBtn.addEventListener("click", () => send(input.value));
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input.value); }
});
input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 120) + "px";
});
document.querySelectorAll(".chip").forEach((c) =>
  c.addEventListener("click", () => send(c.dataset.q))
);
