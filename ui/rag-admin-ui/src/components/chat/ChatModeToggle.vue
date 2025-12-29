<script setup>
const props = defineProps({
  modelValue: {
    type: String,
    required: true,
  },
})

const emit = defineEmits(['update:modelValue'])

function updateMode(value) {
  emit('update:modelValue', value)
}
</script>

<template>
  <div class="flex items-center gap-3 text-xs text-slate-300">
    <span class="uppercase tracking-wider text-slate-400">Chat mode</span>

    <label class="flex items-center gap-1 cursor-pointer">
      <input type="radio" :value="'cloud'" :checked="props.modelValue === 'cloud'" @change="updateMode('cloud')" />
      <span>Cloud</span>
    </label>

    <label class="flex items-center gap-1 cursor-pointer">
      <input type="radio" :value="'local'" :checked="props.modelValue === 'local'" @change="updateMode('local')" />
      <span>Local</span>
    </label>
  </div>
</template>