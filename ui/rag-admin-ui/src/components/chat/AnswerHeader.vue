<script setup>
const props = defineProps({
  isLoading: {
    type: Boolean,
    required: true,
  },
  canSave: {
    type: Boolean,
    required: true,
  },
  saveStatus: {
    type: String,
    required: true,
  },
})

const emit = defineEmits(['save'])
</script>

<template>
  <div class="flex items-center justify-between">
    <h3 class="text-lg font-semibold text-white">LLM Answer</h3>
    <div class="flex items-center gap-3">
    <button
      type="button"
      class="rounded-full border border-slate-500 px-4 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-slate-200 hover:border-slate-300 disabled:opacity-40 disabled:cursor-not-allowed"
      :disabled="!canSave"
      @click="emit('save')"
    >
      Save as note
    </button>

    <span v-if="saveStatus === 'saved'" class="ml-3 text-sm text-emerald-400">
      Saved
    </span>
  </div>
  </div>
</template>