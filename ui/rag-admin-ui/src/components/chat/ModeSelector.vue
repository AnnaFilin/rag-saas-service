<script setup>
  import { computed } from 'vue'
  
  const props = defineProps({
    role: { type: String, required: true },
  })
  
  const emit = defineEmits(['update:role'])
  
  const isRoleActive = computed(() => !!props.role.trim())
  
  function updateRole(value) {
    emit('update:role', value)
  }
  
  function clearRole() {
    emit('update:role', '')
  }
  </script>
  
  <template>
    <div class="flex flex-col gap-2">
      <div class="flex items-center justify-between">
        <label class="text-sm font-semibold text-slate-300">Custom role</label>
  
        <div class="flex items-center gap-2 text-xs">
          <span class="text-slate-400">
            <span :class="isRoleActive ? 'text-emerald-300' : 'text-slate-500'">
              {{ isRoleActive ? 'active' : 'off' }}
            </span>
          </span>
  
          <button
            v-if="isRoleActive"
            type="button"
            class="rounded-md px-2 py-1 text-slate-400 hover:text-white hover:bg-slate-800"
            @click="clearRole"
          >
            Clear
          </button>
        </div>
      </div>
  
      <textarea
        :value="props.role"
        @input="updateRole($event.target.value)"
        class="w-full rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-slate-500"
        rows="3"
        placeholder="Custom instruction for the assistant..."
      ></textarea>
    </div>
  </template>
  