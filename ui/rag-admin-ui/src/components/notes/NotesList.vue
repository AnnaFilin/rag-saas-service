
<script setup>
import NoteListItem from './NoteListItem.vue'

const props = defineProps({
  notes: {
    type: Array,
    required: true,
  },
  isLoading: {
    type: Boolean,
    default: false,
  },
  errorText: {
    type: String,
    default: '',
  },
  selectedId: {
    type: [String, Number],
    default: null,
  },
})

const emit = defineEmits(['select', 'delete'])

</script>

<template>
  <div class="flex flex-col gap-4 min-h-0">
    <div v-if="isLoading" class="flex items-center gap-3 text-xs text-slate-500">
  <div
    class="h-4 w-4 animate-spin rounded-full border-2 border-slate-700 border-t-slate-300"
    aria-label="Loading"
  ></div>
  <span class="italic">Loading notes...</span>
</div>

    <div v-else-if="errorText" class="text-xs text-red-300">{{ errorText }}</div>
    <template v-else>
      <div v-for="item in notes" :key="item.id">
        <NoteListItem
  :item="item"
  :isSelected="selectedId === item.id"
  @select="emit('select', $event)"
  @delete="emit('delete', $event)"
/>

      </div>
      <p v-if="!notes.length" class="text-xs text-slate-500 italic">No notes yet.</p>
    </template>
  </div>
</template>