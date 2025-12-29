<!-- ui/rag-admin-ui/src/components/chat/ChatStatusRow.vue -->
<script setup>
const props = defineProps({
  isLoading: {
    type: Boolean,
    required: true,
  },
  errorText: {
    type: String,
    required: true,
  },
})
</script>

<template>
  <div class="flex items-center justify-between space-x-3">
    <span class="text-sm text-slate-400">
      <div v-if="props.isLoading" class="flex items-center gap-2">
        <div class="h-4 w-4 animate-spin rounded-full border-2 border-slate-400 border-t-transparent"></div>
        <span class="text-sm text-slate-300">Loading...</span>
      </div>

      <span v-else-if="props.errorText" class="text-sm text-red-300">
        {{ props.errorText }}
      </span>

      <span v-else>Ready to submit your question</span>
    </span>
    <span class="text-xs uppercase tracking-[0.2em] text-slate-500">Status</span>
    <div class="h-2 w-24 rounded-full bg-slate-800">
      <div class="h-2 rounded-full bg-emerald-500" :class="props.isLoading ? 'w-12 animate-pulse' : 'w-6'"></div>
    </div>
  </div>
</template>