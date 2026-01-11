<script setup>
import { ref, onMounted } from 'vue'
import Navbar from './components/Navbar.vue'
import Sidebar from './components/Sidebar.vue'
import MainContent from './components/MainContent.vue'

const tabs = ['Chat', 'Notes', 'Docs']
const activeTab = ref('Chat')
const workspaces = ref([])
const selectedWorkspace = ref('')
const isLoadingWorkspaces = ref(false)
const toast = ref('')
let toastTimer = null

function showToast(message, ms = 2500) {
  toast.value = message
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toast.value = ''
    toastTimer = null
  }, ms)
}


function selectWorkspace(name) {
  selectedWorkspace.value = name
}

function changeTab(tab) {
  activeTab.value = tab
}

async function loadWorkspaces() {
  isLoadingWorkspaces.value = true

  try {
    const res = await fetch('/api/rag/workspaces')
    if (!res.ok) throw new Error(`Workspaces request failed (${res.status})`)

    const data = await res.json()
    const list = data?.workspaces || []

    workspaces.value = list

    if (!selectedWorkspace.value && list.length) {
      selectedWorkspace.value = list[0]
    }
  } catch (error) {
    console.error('Unable to fetch workspaces', error)
  } finally {
    isLoadingWorkspaces.value = false
  }
}

async function deleteWorkspace(workspaceId) {
  const ws = (workspaceId || '').trim()
  if (!ws) return

  const ok = window.confirm(`Delete workspace "${ws}"? This will remove its documents, chunks, and notes.`)
  if (!ok) return

  try {
    const res = await fetch(`/api/rag/workspaces/${encodeURIComponent(ws)}`, {
      method: 'DELETE',
    })

    if (!res.ok) {
      const text = await res.text()
      throw new Error(text || `Delete workspace failed (${res.status})`)
    }

    await loadWorkspaces()
    showToast(`Workspace "${ws}" deleted`)


    if (selectedWorkspace.value === ws) {
      selectedWorkspace.value = workspaces.value?.[0] || ''
    }
  } catch (err) {
    console.error('Delete workspace failed', err)
    showToast(err?.message || 'Delete workspace failed', 4000)
  }
}


onMounted(() => {
  loadWorkspaces()
})
</script>

<template>
  <div class="app-shell rag-shell">

    <Navbar />

    <main class="content-shell rag-main">
      <div v-if="toast"
        class="mb-3 rounded-lg border border-emerald-700 bg-emerald-900/30 px-3 py-2 text-xs text-emerald-200">
        {{ toast }}
      </div>

      <div class="content-inner rag-main-inner">

        <Sidebar :workspaces="workspaces" :selectedWorkspace="selectedWorkspace" :isLoading="isLoadingWorkspaces"
          @select="selectWorkspace" @delete="deleteWorkspace" />

        <MainContent :tabs="tabs" :activeTab="activeTab" :selectedWorkspace="selectedWorkspace"
          @change-tab="changeTab" />
      </div>
    </main>
  </div>
</template>