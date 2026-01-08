<script setup>
const props = defineProps({
  item: {
    type: Object,
    required: true,
  },
  isSelected: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['select', 'delete'])


function formatNoteDate(item) {
  const value = item?.created_at || item?.createdAt || item?.date
  if (!value) return '—'
  const text = value.toString()
  if (text.includes('T')) {
    return text.slice(0, 16).replace('T', ' ')
  }
  return text.slice(0, 16)
}
</script>

<template>
  <div :class="['rag-card-soft cursor-pointer border transition-colors', isSelected ? 'border-emerald-400' : 'border-transparent hover:border-emerald-400']">
    <div class="flex items-start gap-2">
  <button class="flex-1 text-left" type="button" @click="emit('select', item.id)">
    <p class="text-sm font-semibold text-white">{{ item.question }}</p>
    <p class="mt-2 text-xs text-slate-400 line-clamp-4">{{ item.answer }}</p>
    <div class="mt-3 flex flex-wrap gap-2 text-[0.65rem] uppercase tracking-[0.2em] text-slate-500">
      <span>{{ formatNoteDate(item) }}</span>
      <span v-if="item.tags && item.tags.length">{{ item.tags.join(', ') }}</span>
      <span v-else class="italic text-slate-600">No tags</span>
    </div>
  </button>

  <button
    type="button"
    class="mt-1 rounded-md px-2 py-1 text-xs text-slate-400 hover:text-white hover:bg-slate-800"
    title="Delete note"
    @click.stop="emit('delete', item.id)"
  >
    Delete
  </button>
</div>

  </div>
</template>
