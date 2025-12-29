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
  successText: {
    type: String,
    required: true,
  },
})
</script>

<template>
  <div class="flex items-center justify-between text-sm text-slate-400">
    <span>
      <span v-if="props.isLoading">Loading...</span>
      <span v-else-if="props.errorText" class="text-sm text-red-300">{{ props.errorText }}</span>
      <span v-else-if="props.successText">{{ props.successText }}</span>
      <span v-else>Ready to upload your document</span>
    </span>
    <span class="text-[0.65rem] uppercase tracking-[0.3em] text-slate-500">Idle</span>
    <div class="h-2 w-24 rounded-full bg-slate-800">
      <div class="h-2 rounded-full bg-emerald-500" :class="props.isLoading ? 'w-12 animate-pulse' : 'w-6'"></div>
    </div>
  </div>
</template>