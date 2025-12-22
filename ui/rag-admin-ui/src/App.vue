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



onMounted(() => {
  loadWorkspaces()
})
</script>

<template>
    <div class="app-shell rag-shell">

    <Navbar />

    <main
  class="content-shell rag-main"
>
      <div
  class="content-inner rag-main-inner"
>

        <Sidebar
          :workspaces="workspaces"
          :selectedWorkspace="selectedWorkspace"
          :isLoading="isLoadingWorkspaces"
          @select="selectWorkspace"
        />

        <MainContent
          :tabs="tabs"
          :activeTab="activeTab"
          :selectedWorkspace="selectedWorkspace"
          @change-tab="changeTab"
        />
      </div>
    </main>
  </div>
</template>