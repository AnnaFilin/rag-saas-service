<script setup>
  import NoteSources from './NoteSources.vue'
  
  const props = defineProps({
    note: {
      type: Object,
      default: null,
    },
  })
  
  function formatNoteDate(note) {
    const value = note?.created_at || note?.createdAt || note?.date
    if (!value) return '—'
    const text = value.toString()
    if (text.includes('T')) {
      return text.slice(0, 16).replace('T', ' ')
    }
    return text.slice(0, 16)
  }
  </script>
  
  <template>
    <template v-if="note">
      <header class="flex items-center justify-between">
        <h3 class="text-base font-semibold text-white">Selected note</h3>
        <span class="text-xs text-slate-500 uppercase tracking-[0.3em]">
          {{ formatNoteDate(note) }}
        </span>
      </header>
  
      <div class="rag-card-soft flex-1 flex flex-col gap-3 min-h-0 overflow-auto">

        <p class="text-sm font-semibold text-white whitespace-pre-wrap">
          {{ note.question }}
        </p>
  
        <p class="text-sm text-slate-200 whitespace-pre-wrap">
          {{ note.answer }}
        </p>
  
        <NoteSources :sources="note.sources" />
      </div>
    </template>
  
    <template v-else>
      <div class="rag-card-soft flex-1 flex flex-col items-center justify-center text-slate-500 text-sm">
        No note selected.
      </div>
    </template>
  </template>
  