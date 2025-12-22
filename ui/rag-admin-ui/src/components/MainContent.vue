<template>
    <section class="rag-card flex flex-col gap-4 h-full">
      <section
        class="flex justify-between items-center bg-slate-900/40 rounded-xl px-4 py-3 text-xs text-slate-400"
      >
        <div>
          <p
            class="m-0 text-[0.7rem] tracking-[0.18em] uppercase text-slate-500"
          >
            Current workspace
          </p>
          <p class="m-0 mt-1 font-semibold text-sm text-slate-100">
            {{ selectedWorkspace }}
          </p>
        </div>
        <div class="text-right">
          <p
            class="m-0 text-[0.7rem] tracking-[0.18em] uppercase text-slate-500"
          >
            Status
          </p>
          <p class="m-0 mt-1 font-semibold text-sm text-emerald-400">
            Connected
          </p>
        </div>
      </section>
  
      <section class="flex gap-4 border-b border-slate-800 mt-2">
        <button
          v-for="tab in tabs"
          :key="tab"
          type="button"
          class="rag-tab"
          :class="{ 'rag-tab-active': activeTab === tab }"
          @click="changeTab(tab)"
        >
          {{ tab }}
        </button>
      </section>
  
      <section class="rag-card-soft flex-1 mt-2 text-sm text-slate-200">
  <div v-if="activeTab === 'Chat'" class="h-full">
    <Chat :workspace-id="selectedWorkspace" :key="selectedWorkspace" @save-note="handleSaveNote"/>
  </div>

  <div v-else-if="activeTab === 'Notes'" class="h-full">
    <Notes :workspace-id="selectedWorkspace" :key="selectedWorkspace" />
  </div>

  <div v-else class="h-full">
    <Docs :workspace-id="selectedWorkspace" :key="selectedWorkspace" />
  </div>
</section>

    </section>
  </template>
  
  
  <script setup>
 
  import Chat from './Chat.vue'
  import Docs from './Docs.vue'
  import Notes from './Notes.vue'


  const props = defineProps({
    tabs: {
      type: Array,
      required: true
    },
    activeTab: {
      type: String,
      required: true
    },
    selectedWorkspace: {
      type: String,
      required: true
    }
  })
  
  const emit = defineEmits(['change-tab'])
  
  function changeTab(tab) {
    emit('change-tab', tab)
  }

  async function handleSaveNote(payload) {
  try {
    const res = await fetch('/api/rag/notes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspace_id: payload.workspaceId,
        question: payload.question,
        answer: payload.answer,
        sources: Array.isArray(payload.sources) ? payload.sources : [],
      }),
    })

    if (!res.ok) {
      const text = await res.text()
      throw new Error(text || `Save note failed: ${res.status}`)
    }
  } catch (err) {
    console.error('Save note failed', err)
  }
}

  </script>