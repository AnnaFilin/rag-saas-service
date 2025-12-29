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

const emit = defineEmits(['select'])

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
    <button class="w-full text-left" type="button" @click="emit('select', item.id)">
      <p class="text-sm font-semibold text-white">{{ item.question }}</p>
      <p class="mt-2 text-xs text-slate-400 line-clamp-4">{{ item.answer }}</p>
      <div class="mt-3 flex flex-wrap gap-2 text-[0.65rem] uppercase tracking-[0.2em] text-slate-500">
        <span>{{ formatNoteDate(item) }}</span>
        <span v-if="item.tags && item.tags.length">{{ item.tags.join(', ') }}</span>
        <span v-else class="italic text-slate-600">No tags</span>
      </div>
    </button>
  </div>
</template>
