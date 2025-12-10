(function () {
    setupChat();
    setupIngest();
    loadWorkspaces();
  
    function loadWorkspaces() {
      fetch("https://rag-saas-rag-630957115938.me-west1.run.app/workspaces")
        .then((res) => res.json())
        .then((data) => {
          const datalist = document.getElementById("workspace-list");
          if (!datalist) return;
  
          datalist.innerHTML = "";
          const ids = Array.isArray(data.workspaces) ? data.workspaces : [];
          ids.forEach((id) => {
            const opt = document.createElement("option");
            opt.value = id;
            datalist.appendChild(opt);
          });
        })
        .catch(() => {
          // quietly ignore the error, just without autocomplete
        });
    }
  
    function setupChat() {
      const chatForm = document.querySelector('form[action="/chat"]');
      const resultEl = document.getElementById("chat-result");
      const chatError = document.getElementById("chat-error");
  
      if (!chatForm || !resultEl) return;
  
      chatForm.addEventListener("submit", async (event) => {
        event.preventDefault();
  
        const formData = new FormData(chatForm);
        const workspace_id = (formData.get("workspace_id") || "").toString();
        const question = (formData.get("question") || "").toString();
        let role = formData.get("role");
        role = role && role.toString().trim() ? role.toString() : null;
  
        resultEl.textContent = "LLM thinking…";
        if (chatError) {
          chatError.textContent = "";
        }
  
        try {
        //   const response = await fetch(
        //     "https://rag-saas-rag-630957115938.me-west1.run.app/chat",
        //     {
        //       method: "POST",
        //       headers: { "Content-Type": "application/json" },
        //       body: JSON.stringify({ workspace_id, question, role }),
        //     },
        //   );
        const response = await fetch(
            "http://localhost:8000/chat",   // локально
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ workspace_id, question, role }),
            },
          );
          
  
          if (!response.ok) {
            throw new Error("Request failed: " + response.status);
          }
  
          const data = await response.json();
          resultEl.innerHTML = "";
  
          const answerEl = document.createElement("p");
          answerEl.textContent = "Answer: " + (data.answer || "");
          resultEl.appendChild(answerEl);
  
          if (Array.isArray(data.sources) && data.sources.length) {
            const sourcesList = document.createElement("ul");
            data.sources.forEach((source) => {
              const item = document.createElement("li");
              const src = source.source || "unknown";
              const snippet =
                (source.content && source.content.slice(0, 120)) || "";
              item.textContent = `${src} — ${snippet}`;
              sourcesList.appendChild(item);
            });
            resultEl.appendChild(sourcesList);
          }
  
          if (chatError) {
            chatError.textContent = "";
          }
        } catch (error) {
          if (chatError) {
            chatError.textContent = "Error: " + error.message;
          }
        }
      });
    }
  
    function setupIngest() {
      const ingestForm = document.getElementById("ingest-form");
      const ingestResult = document.getElementById("ingest-result");
      const ingestError = document.getElementById("ingest-error");
  
      if (!ingestForm || !ingestResult) return;
  
      ingestForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        ingestResult.textContent = "Uploading document…";
        if (ingestError) {
          ingestError.textContent = "";
        }
  
        const formData = new FormData(ingestForm);
  
        try {
          const response = await fetch(
            "https://rag-saas-ingest-630957115938.me-west1.run.app/ingest-file",
            {
              method: "POST",
              body: formData,
            },
          );
  
          if (!response.ok) {
            throw new Error("Request failed: " + response.status);
          }
  
          const data = await response.json();
          ingestResult.innerHTML = `
              Workspace: ${data.workspace_id || "n/a"}<br />
              Chunks: ${data.chunks_count ?? 0}<br />
              Embeddings: ${data.embeddings_count ?? 0}<br />
              Errors: ${(data.errors || []).join(", ") || "none"}
            `;
          if (ingestError) {
            ingestError.textContent = "";
          }
        } catch (error) {
          if (ingestError) {
            ingestError.textContent = "Error: " + error.message;
          }
        }
      });
    }
  })();