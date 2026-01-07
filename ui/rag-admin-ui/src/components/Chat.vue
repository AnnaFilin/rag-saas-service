<script setup>
import AnswerSources from './chat/AnswerSources.vue'
import ModeSelector from './chat/ModeSelector.vue'
import QuestionInput from './chat/QuestionInput.vue'
import ChatModeToggle from './chat/ChatModeToggle.vue'
import ChatStatusRow from './chat/ChatStatusRow.vue'
import AskButton from './chat/AskButton.vue'
import AnswerHeader from './chat/AnswerHeader.vue'
import ErrorBanner from './common/ErrorBanner.vue'

import { ref } from 'vue'

const props = defineProps({
    workspaceId: { type: String, required: true },
})

const question = ref('')
const role = ref('')
const isLoading = ref(false)
const errorText = ref('')
const saveStatus = ref('')
const ragMode = ref('reference')
const answer = ref('')
const sources = ref([])
const chatMode = ref('local') // 'cloud' | 'local'
let saveTimerId = null

const CHAT_ENDPOINTS = {
    cloud: '/api/rag/chat',
    local: 'http://localhost:8000/chat',
}

const emit = defineEmits(['save-note'])

const showAllSources = ref(false)

async function submitQuestion() {
    showAllSources.value = false

    if (!question.value.trim()) {
        return
    }

    isLoading.value = true
    errorText.value = ''
    answer.value = ''
    sources.value = []
    const endpoint = CHAT_ENDPOINTS[chatMode.value]


    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                workspace_id: props.workspaceId,
                question: question.value,
                // mode: ragMode.value, // "reference" | "synthesis" | "custom"
                role: ragMode.value === 'custom' && role.value.trim() ? role.value : null,
            }),
        })

        if (!response.ok) {
            throw new Error(`Request failed: ${response.status}`)
        }

        const data = await response.json()

        console.log('endpoint:', endpoint)
        console.log('source sample:', data.sources?.[0])

        answer.value = data.answer || ''
        sources.value = Array.isArray(data.sources) ? data.sources : []
    } catch (error) {
        errorText.value = error.message
    } finally {
        isLoading.value = false
    }
}

function saveCurrentNote() {
    if (!answer.value.trim()) return
    if (!props.workspaceId) return

    const normalizedSources = (sources.value || [])
        .map((item) => {
            if (!item) return null
            if (typeof item === 'string') {
                const trimmed = item.trim()
                return { source: trimmed || 'Unknown source' }
            }
            if (typeof item === 'object') {
                const sourceValue = (item.source || '').toString().trim() || 'Unknown source'
                return {
                    source: sourceValue,
                    chunk_index: item.chunk_index,
                    chunk_id: item.chunk_id,
                    content: item.content,
                }
            }
            return null
        })
        .filter(Boolean)

    saveStatus.value = 'saving'
    if (saveTimerId) {
        clearTimeout(saveTimerId)
        saveTimerId = null
    }

    emit('save-note', {
        question: question.value,
        answer: answer.value,
        sources: normalizedSources,
        workspaceId: props.workspaceId,
        createdAt: new Date().toISOString(),
    })

    saveStatus.value = 'saved'
    saveTimerId = setTimeout(() => {
        saveStatus.value = ''
        saveTimerId = null
    }, 2500)
}



</script>

<template>
    <section class="flex flex-col gap-4 h-full">
        <div class="rag-card-soft flex flex-col gap-3">
            <QuestionInput :modelValue="question" @update:modelValue="question = $event" />

            <ModeSelector :ragMode="ragMode" :role="role" @update:ragMode="ragMode = $event"
                @update:role="role = $event" />

            <ChatStatusRow :isLoading="isLoading" :errorText="errorText" />

            <ChatModeToggle :modelValue="chatMode" @update:modelValue="chatMode = $event" />

            <AskButton :disabled="isLoading || !question.trim()" @click="submitQuestion" />
        </div>

        <div class="rag-card flex-1 flex flex-col gap-3">

            <AnswerHeader :isLoading="isLoading" :canSave="!!answer.trim() && !isLoading" :saveStatus="saveStatus"
                @save="saveCurrentNote" />
            <div class="flex-1 rounded-lg border border-slate-800 bg-slate-950 p-4 text-sm text-slate-100">
                {{ answer }}

                <AnswerSources :sources="sources" :answer="answer" />
            </div>

            <ErrorBanner v-if="errorText" :text="errorText" />
        </div>
    </section>
</template>