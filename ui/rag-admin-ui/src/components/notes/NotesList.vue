
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

const emit = defineEmits(['select'])
</script>

<template>
  <div class="flex flex-col gap-4 min-h-0">
    <div v-if="isLoading" class="text-xs text-slate-500 italic">Loading notes...</div>
    <div v-else-if="errorText" class="text-xs text-red-300">{{ errorText }}</div>
    <template v-else>
      <div v-for="item in notes" :key="item.id">
        <NoteListItem
          :item="item"
          :isSelected="selectedId === item.id"
          @select="emit('select', $event)"
        />
      </div>
      <p v-if="!notes.length" class="text-xs text-slate-500 italic">No notes yet.</p>
    </template>
  </div>
</template>