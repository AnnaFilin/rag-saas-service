
<template>
      <aside class="rag-card flex flex-col h-full">
    <h3 class="mb-4 text-center text-sm font-medium text-slate-200">
      Workspaces
    </h3>
    <div class="mb-4">
  <div class="flex w-full items-stretch gap-2">
    <input
      v-model="newWorkspaceId"
      @keyup.enter="useNewWorkspace"
      class="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-slate-500"
      type="text"
      placeholder="New workspace id..."
    />
    <button
      type="button"
      @click="useNewWorkspace"
      class="shrink-0 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm font-medium text-slate-200 hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-500"
      aria-label="Use new workspace"
      title="Use"
    >
      Use
    </button>
  </div>
</div>

<div class="mt-3">
  <div v-if="isLoading" class="flex items-center gap-2 py-2 text-sm text-slate-400">
  <div class="h-4 w-4 animate-spin rounded-full border-2 border-slate-400 border-t-transparent"></div>
  <span>Loading workspaces…</span>
</div>
    <ul class="space-y-2">
        <li
          v-for="workspace in workspaces"
          :key="workspace"
          class="w-full"
          :class="{ active: selectedWorkspace === workspace }"
        >
        <button
          type="button"
          @click="handleSelection(workspace)"
          class="w-full text-left px-3 py-2 rounded-lg text-sm font-medium
                 truncate
                 bg-slate-900/60 text-slate-200 hover:bg-slate-800
                 border border-transparent
                 transition
                "
          :class="{
            'bg-blue-600 text-white border-blue-500': selectedWorkspace === workspace
          }"
        >
            {{ workspace }}
          </button>
        </li>
      </ul>
</div>
    </aside>
  </template>

  <script setup>
  import { ref, watch } from 'vue'
  
  const props = defineProps({
    workspaces: {
      type: Array,
      required: true
    },
    selectedWorkspace: {
      type: String,
      required: true
    },
    isLoading: {
    type: Boolean,
    default: false
  }
  })

  const emit = defineEmits(['select'])

  const newWorkspaceId = ref('')
  const isLoadingWorkspaces = ref(props.isLoading)

  watch(
  () => props.isLoading,
  (value) => {
    isLoadingWorkspaces.value = value
  },
  { immediate: true }
)



  function useNewWorkspace() {
  const id = newWorkspaceId.value.trim()
  if (!id) return
  newWorkspaceId.value = ''
  emit('select', id)
}

  function handleSelection(workspace) {
    emit('select', workspace)
  }
  </script>