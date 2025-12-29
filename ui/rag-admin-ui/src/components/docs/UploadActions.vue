<script setup>
const props = defineProps({
  selectedFile: {
    type: Object,
    default: null,
  },
  isLoading: {
    type: Boolean,
    required: true,
  },
})

const emit = defineEmits(['upload', 'upload-book'])
</script>

<template>
  <div class="flex flex-wrap gap-3">
    <button
      class="rounded-full border border-slate-600 px-3 py-1 text-xs font-semibold text-slate-200 hover:border-white"
      type="button"
      :disabled="!props.selectedFile || props.isLoading"
      @click="emit('upload')"
    >
      Upload
    </button>
    <button
      class="rounded-full border border-slate-600 px-3 py-1 text-xs font-semibold text-slate-200 hover:border-white"
      type="button"
      :disabled="props.isLoading"
      @click="emit('upload-book')"
    >
      Upload book (local)
    </button>
  </div>
</template>