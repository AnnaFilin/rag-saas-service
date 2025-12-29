<script setup>
const props = defineProps({
  upload: {
    type: Object,
    required: true,
  },
})
</script>

<template>
  <li
    class="rounded-lg border border-slate-800 bg-slate-950 p-3 text-sm text-slate-200 flex flex-col gap-1"
  >
    <div class="flex items-center justify-between">
      <span class="font-semibold">{{ props.upload.name }}</span>
      <span class="text-xs text-slate-400">{{ props.upload.size }}</span>
    </div>
    <div class="flex flex-wrap items-center gap-2 text-xs text-slate-400">
      <span>Chunks: {{ props.upload.chunks }}</span>
      <span class="flex items-center gap-1">
        Status:
        <span class="rounded-full bg-slate-800 px-2 py-0.5 text-[0.6rem] uppercase tracking-[0.2em]">
          {{ props.upload.status }}
        </span>
      </span>
    </div>
  </li>
</template>