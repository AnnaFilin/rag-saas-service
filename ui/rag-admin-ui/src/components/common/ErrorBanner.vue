<script setup>
const props = defineProps({
  text: {
    type: String,
    required: true,
  },
})
</script>

<template>
  <div class="rounded-md border border-red-600 bg-red-700/40 px-4 py-2 text-sm text-red-200">
    {{ props.text }}
  </div>
</template>