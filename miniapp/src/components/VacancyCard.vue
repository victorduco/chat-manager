<template>
  <div class="card vacancy-card" @click="$emit('click', vacancy)">
    <div class="card-header">
      <h3 class="card-title">{{ vacancy.title }}</h3>
      <span class="company">{{ vacancy.company }}</span>
    </div>
    <div class="card-info">
      <span class="info-item">📍 {{ vacancy.location }}</span>
      <span class="info-item salary">💰 {{ vacancy.salary }}</span>
    </div>
    <div class="card-tags">
      <span v-for="tag in vacancy.tags" :key="tag" class="tag">{{ tag }}</span>
    </div>
  </div>
</template>

<script>
export default {
  name: 'VacancyCard',
  props: {
    vacancy: {
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

.card-header {
  margin-bottom: 12px;
}

.card-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--tg-theme-text-color, #000000);
  margin: 0 0 4px 0;
}

.company {
  font-size: 14px;
  color: var(--tg-theme-hint-color, #999999);
}

.card-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}

.info-item {
  font-size: 14px;
  color: var(--tg-theme-text-color, #000000);
}

.salary {
  font-weight: 600;
  color: var(--tg-theme-button-color, #3390ec);
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
