<script setup>
const props = defineProps({
  modelValue: {
    type: String,
    required: true,
  },
})

const emit = defineEmits(['update:modelValue'])

function updateValue(value) {
  emit('update:modelValue', value)
}
</script>

<template>
  
    <label class="text-sm font-semibold text-slate-300">Question</label>
    <textarea
      :value="props.modelValue"
      @input="updateValue($event.target.value)"
      class="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-slate-500"
      rows="3"
      placeholder="Type your question..."
    ></textarea>
 
</template>