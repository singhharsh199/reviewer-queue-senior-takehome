<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  applyReviewAction,
  fetchReviewItems,
  type ReviewAction,
  type ReviewItem
} from "./api";

const currentReviewer = "alex";
const items = ref<ReviewItem[]>([]);
const selectedId = ref<string | null>(null);
const isLoading = ref(false);
const errorMessage = ref<string | null>(null);
const pendingAction = ref<ReviewAction | null>(null);

const activeTab = ref<"to_claim" | "my_tasks" | "others" | "completed">("to_claim");
const searchQuery = ref("");

// counts based on current items loaded
const countToClaim = computed(() => items.value.filter(i => i.status === "unassigned").length);
const countMyTasks = computed(() => items.value.filter(i => i.status === "in_review" && i.assigned_reviewer === currentReviewer).length);
const countOthers = computed(() => items.value.filter(i => i.status === "in_review" && i.assigned_reviewer !== currentReviewer).length);
const countCompleted = computed(() => items.value.filter(i => ["approved", "rejected", "escalated"].includes(i.status)).length);

const filteredItems = computed(() => {
  const query = searchQuery.value.toLowerCase().trim();
  
  let tabItems = items.value;
  if (activeTab.value === "to_claim") {
    tabItems = items.value.filter(item => item.status === "unassigned");
  } else if (activeTab.value === "my_tasks") {
    tabItems = items.value.filter(item => item.status === "in_review" && item.assigned_reviewer === currentReviewer);
  } else if (activeTab.value === "others") {
    tabItems = items.value.filter(item => item.status === "in_review" && item.assigned_reviewer !== currentReviewer);
  } else if (activeTab.value === "completed") {
    tabItems = items.value.filter(item => ["approved", "rejected", "escalated"].includes(item.status));
  }

  if (!query) return tabItems;
  return tabItems.filter(item => 
    item.title.toLowerCase().includes(query) ||
    item.id.toLowerCase().includes(query) ||
    (item.summary && item.summary.toLowerCase().includes(query))
  );
});

const selectedItem = computed(() => {
  if (selectedId.value) {
    const found = items.value.find((item) => item.id === selectedId.value);
    if (found) return found;
  }
  return filteredItems.value[0] ?? null;
});

async function loadItems() {
  isLoading.value = true;
  errorMessage.value = null;

  try {
    items.value = await fetchReviewItems(false);
    
    // Select first item of current tab if any exists
    const tabItems = filteredItems.value;
    if (tabItems.length > 0) {
      selectedId.value = tabItems[0].id;
    } else {
      selectedId.value = null;
    }
  } catch (error) {
    errorMessage.value = "Something went wrong loading the queue.";
  } finally {
    isLoading.value = false;
  }
}

function selectTab(tab: typeof activeTab.value) {
  activeTab.value = tab;
  searchQuery.value = ""; // Clear search when changing tabs
  
  const tabItems = items.value.filter(item => {
    if (tab === "to_claim") return item.status === "unassigned";
    if (tab === "my_tasks") return item.status === "in_review" && item.assigned_reviewer === currentReviewer;
    if (tab === "others") return item.status === "in_review" && item.assigned_reviewer !== currentReviewer;
    return ["approved", "rejected", "escalated"].includes(item.status);
  });
  
  if (tabItems.length > 0) {
    selectedId.value = tabItems[0].id;
  } else {
    selectedId.value = null;
  }
}

async function performAction(action: ReviewAction) {
  if (!selectedItem.value) return;

  pendingAction.value = action;
  errorMessage.value = null;

  try {
    const updated = await applyReviewAction(selectedItem.value.id, action, currentReviewer);
    items.value = items.value.map((item) => (item.id === updated.id ? updated : item));
    
    // TAKEHOME: UX improvement - Auto navigate to appropriate tabs after action
    if (action === "claim") {
      activeTab.value = "my_tasks";
      selectedId.value = updated.id;
    } else if (["approve", "reject", "escalate"].includes(action)) {
      activeTab.value = "completed";
      selectedId.value = updated.id;
    }
  } catch (error: any) {
    errorMessage.value = error.message || "That action could not be completed.";
  } finally {
    pendingAction.value = null;
  }
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

function getTimeline(item: ReviewItem) {
  const timeline = [
    {
      time: item.submitted_at,
      title: "Queue Item Created",
      description: "Submitted automatically by compliance scoring engine.",
      type: "system"
    }
  ];
  
  if (item.status === "in_review") {
    timeline.push({
      time: item.submitted_at,
      title: "Claimed & Owned",
      description: `Claimed by ${item.assigned_reviewer}. State changed to in_review.`,
      type: "user"
    });
  } else if (["approved", "rejected", "escalated"].includes(item.status)) {
    timeline.push({
      time: item.submitted_at,
      title: "Claimed & Owned",
      description: `Claimed by ${item.assigned_reviewer}. State changed to in_review.`,
      type: "user"
    });
    let dec = "Approved";
    let desc = "Decision finalized. Item marked as approved.";
    if (item.status === "rejected") {
      dec = "Rejected";
      desc = "Review rejected. Notification sent to customer.";
    } else if (item.status === "escalated") {
      dec = "Escalated";
      desc = "Escalated to Tier-2 operations manager for further review.";
    }
    timeline.push({
      time: item.submitted_at,
      title: dec,
      description: desc,
      type: "terminal"
    });
  }
  return timeline;
}

onMounted(loadItems);
</script>

<template>
  <main class="page-shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">Reviewer Workspace</p>
        <h1>Reviewer Queue</h1>
      </div>
      <div class="reviewer-card">
        <div class="avatar">A</div>
        <div>
          <span class="reviewer-name">{{ currentReviewer }}</span>
          <span class="reviewer-role">Operations Reviewer</span>
        </div>
      </div>
    </header>

    <div v-if="errorMessage" class="error-banner">
      <svg class="error-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
      <span>{{ errorMessage }}</span>
      <button class="close-error" @click="errorMessage = null">&times;</button>
    </div>
    
    <div v-if="isLoading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading queue items...</p>
    </div>

    <section v-else class="workspace">
      <!-- SIDEBAR -->
      <aside class="sidebar" aria-label="Review queue sidebar">
        <!-- Search bar -->
        <div class="search-container">
          <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search items by ID, title..."
            class="search-input"
            aria-label="Search items"
          />
          <button v-if="searchQuery" class="clear-search" @click="searchQuery = ''">&times;</button>
        </div>

        <!-- Tabs Navigation -->
        <nav class="queue-tabs" aria-label="Queue filter tabs">
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'to_claim' }"
            type="button"
            @click="selectTab('to_claim')"
          >
            <span>To Claim</span>
            <span class="tab-count">{{ countToClaim }}</span>
          </button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'my_tasks' }"
            type="button"
            @click="selectTab('my_tasks')"
          >
            <span>My Tasks</span>
            <span class="tab-count">{{ countMyTasks }}</span>
          </button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'others' }"
            type="button"
            @click="selectTab('others')"
          >
            <span>Others</span>
            <span class="tab-count">{{ countOthers }}</span>
          </button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'completed' }"
            type="button"
            @click="selectTab('completed')"
          >
            <span>Done</span>
            <span class="tab-count">{{ countCompleted }}</span>
          </button>
        </nav>

        <!-- Queue Items List -->
        <div class="queue-list-container">
          <div v-if="filteredItems.length === 0" class="empty-list">
            <p>No items found</p>
          </div>
          <button
            v-for="item in filteredItems"
            :key="item.id"
            class="queue-card"
            :class="{ selected: item.id === selectedItem?.id }"
            type="button"
            @click="selectedId = item.id"
          >
            <div class="card-header">
              <span class="card-id">{{ item.id }}</span>
              <span class="card-date">{{ formatDate(item.submitted_at).split(' at ')[0] }}</span>
            </div>
            
            <h3 class="card-title">{{ item.title }}</h3>
            
            <div class="card-badges">
              <!-- Risk Pill -->
              <span class="badge" :class="`badge-risk-${item.risk_level}`">
                {{ item.risk_level }}
              </span>
              
              <!-- Customer Tier Pill -->
              <span v-if="item.customer_tier === 'priority'" class="badge badge-priority">
                <svg class="badge-icon" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/>
                </svg>
                Priority
              </span>
              
              <!-- Assignee pill if assigned and not me -->
              <span v-if="item.assigned_reviewer && item.assigned_reviewer !== currentReviewer" class="badge badge-reviewer">
                {{ item.assigned_reviewer }}
              </span>
            </div>
          </button>
        </div>
      </aside>

      <!-- DETAIL VIEW -->
      <section v-if="selectedItem" class="detail-panel">
        <div class="detail-header-card">
          <div class="header-left">
            <div class="id-row">
              <span class="detail-id">{{ selectedItem.id }}</span>
              <span v-if="selectedItem.customer_tier === 'priority'" class="vip-badge">
                <svg class="badge-icon" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/>
                </svg>
                Priority Customer
              </span>
            </div>
            <h2 class="detail-title">{{ selectedItem.title }}</h2>
          </div>
          <div class="header-right">
            <span class="status-badge" :class="`status-${selectedItem.status}`">
              {{ selectedItem.status.replace('_', ' ') }}
            </span>
          </div>
        </div>

        <div class="facts-grid">
          <div class="fact-card">
            <div class="fact-label">Submitted On</div>
            <div class="fact-value">{{ formatDate(selectedItem.submitted_at) }}</div>
          </div>
          <div class="fact-card">
            <div class="fact-label">Risk Assessment</div>
            <div class="fact-value flex-align">
              <span class="risk-indicator" :class="selectedItem.risk_level"></span>
              <span class="capitalize">{{ selectedItem.risk_level }} Risk</span>
            </div>
          </div>
          <div class="fact-card">
            <div class="fact-label">Assigned Owner</div>
            <div class="fact-value flex-align">
              <svg class="fact-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
              </svg>
              <span>{{ selectedItem.assigned_reviewer ?? "Unassigned" }}</span>
            </div>
          </div>
          <div class="fact-card">
            <div class="fact-label">Customer Segment</div>
            <div class="fact-value capitalize">{{ selectedItem.customer_tier }}</div>
          </div>
        </div>

        <!-- Description / Summary -->
        <div class="detail-section">
          <h4 class="section-title">Case Summary</h4>
          <p class="case-summary">{{ selectedItem.summary }}</p>
        </div>

        <!-- Action / Workflow Banner -->
        <div class="workflow-card">
          <h4 class="section-title">Workflow Actions</h4>
          
          <!-- State: Unassigned -->
          <div v-if="selectedItem.status === 'unassigned'" class="action-prompt claim-prompt">
            <div class="prompt-text">
              <strong>This task is unassigned.</strong> Claim it to start your review.
            </div>
            <button
              type="button"
              class="btn btn-primary btn-claim"
              :disabled="Boolean(pendingAction)"
              @click="performAction('claim')"
            >
              <span v-if="pendingAction === 'claim'" class="mini-spinner"></span>
              Claim Task
            </button>
          </div>

          <!-- State: In Review (Assigned to Me) -->
          <div v-else-if="selectedItem.status === 'in_review' && selectedItem.assigned_reviewer === currentReviewer" class="action-prompt action-group">
            <div class="prompt-text">
              <strong>Action required.</strong> Review the details above and log your final decision:
            </div>
            <div class="btn-group">
              <button
                type="button"
                class="btn btn-success"
                :disabled="Boolean(pendingAction)"
                @click="performAction('approve')"
              >
                <span v-if="pendingAction === 'approve'" class="mini-spinner"></span>
                Approve Case
              </button>
              <button
                type="button"
                class="btn btn-danger"
                :disabled="Boolean(pendingAction)"
                @click="performAction('reject')"
              >
                <span v-if="pendingAction === 'reject'" class="mini-spinner"></span>
                Reject Case
              </button>
              <button
                type="button"
                class="btn btn-warning"
                :disabled="Boolean(pendingAction)"
                @click="performAction('escalate')"
              >
                <span v-if="pendingAction === 'escalate'" class="mini-spinner"></span>
                Escalate Case
              </button>
            </div>
          </div>

          <!-- State: In Review (Assigned to Others) -->
          <div v-else-if="selectedItem.status === 'in_review'" class="action-prompt locked-prompt">
            <svg class="prompt-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
              <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
            </svg>
            <div class="prompt-text">
              <strong>Locked Case.</strong> This item is currently being reviewed by <strong>{{ selectedItem.assigned_reviewer }}</strong>. Only the assigned reviewer can make decisions on this item.
            </div>
          </div>

          <!-- State: Terminal -->
          <div v-else class="action-prompt terminal-prompt" :class="`terminal-${selectedItem.status}`">
            <svg class="prompt-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            <div class="prompt-text">
              <strong>Terminal State.</strong> This case was marked as <strong class="capitalize">{{ selectedItem.status }}</strong> by <strong>{{ selectedItem.assigned_reviewer }}</strong>. No further actions are allowed.
            </div>
          </div>
        </div>

        <!-- Case History Timeline -->
        <div class="detail-section timeline-section">
          <h4 class="section-title">Case Activity Timeline ({{ selectedItem.notes_count }} entries)</h4>
          <div class="timeline">
            <div v-for="(log, idx) in getTimeline(selectedItem)" :key="idx" class="timeline-item" :class="log.type">
              <div class="timeline-bullet"></div>
              <div class="timeline-content">
                <div class="timeline-header">
                  <h5>{{ log.title }}</h5>
                  <span class="timeline-time">{{ formatDate(log.time) }}</span>
                </div>
                <p>{{ log.description }}</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- EMPTY STATE -->
      <section v-else class="detail-panel empty-detail">
        <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"></circle>
          <path d="M8 12h8"></path>
        </svg>
        <h3>No case selected</h3>
        <p>Choose an item from the queue list to view details and perform actions.</p>
      </section>
    </section>
  </main>
</template>
