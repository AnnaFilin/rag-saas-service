<script setup>
import UploadListItem from './UploadListItem.vue'

const props = defineProps({
  uploads: {
    type: Array,
    required: true,
  },
})
</script>

<template>
  <div class="rag-card flex-1 flex flex-col gap-4 overflow-hidden">
    <div class="flex items-center justify-between border-b border-slate-800 px-4 py-3">
      <h3 class="text-base font-semibold text-white">Uploaded documents</h3>
      <span class="text-xs uppercase tracking-[0.3em] text-slate-500">{{ props.uploads.length }} files</span>
    </div>
    <ul class="flex-1 px-4 pb-4 space-y-3 overflow-y-auto">
      <UploadListItem
        v-for="upload in props.uploads"
        :key="upload.id || upload.name"
        :upload="upload"
      />
    </ul>
  </div>
</template>