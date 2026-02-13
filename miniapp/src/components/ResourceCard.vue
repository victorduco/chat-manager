<template>
  <div class="card resource-card" @click="$emit('click', resource)">
    <div class="resource-header">
      <div class="resource-icon">📚</div>
      <div class="resource-info">
        <h3 class="card-title">{{ resource.title }}</h3>
        <span class="resource-type">{{ resource.type }}</span>
      </div>
    </div>
    <div class="card-tags">
      <span v-for="tag in resource.tags" :key="tag" class="tag">{{ tag }}</span>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ResourceCard',
  props: {
    resource: {
      type: Object,
      required: true
    }
  }
}
</script>

<style scoped>
.card {
  background: var(--tg-theme-bg-color, #ffffff);
  border-radius: 12px;
  padding: 16px;
  margin: 8px 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.card:active {
  transform: scale(0.98);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}

.resource-header {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.resource-icon {
  font-size: 36px;
  width: 50px;
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--tg-theme-secondary-bg-color, #f0f0f0);
  border-radius: 12px;
  flex-shrink: 0;
}

.resource-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--tg-theme-text-color, #000000);
  margin: 0;
}

.resource-type {
  font-size: 14px;
  color: var(--tg-theme-hint-color, #999999);
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag {
  font-size: 12px;
  padding: 4px 10px;
  background: var(--tg-theme-secondary-bg-color, #f0f0f0);
  color: var(--tg-theme-text-color, #000000);
  border-radius: 12px;
}
</style>
