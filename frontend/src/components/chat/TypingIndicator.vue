<template>
  <div class="typing">
    <span class="typing__dot"></span>
    <span class="typing__dot"></span>
    <span class="typing__dot"></span>
  </div>
</template>

<style scoped lang="scss">
.typing {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 12px 16px;
  background: var(--sl-bg-elevated);
  border: 1px solid var(--sl-border);
  border-radius: var(--sl-radius-lg);
  border-bottom-left-radius: var(--sl-radius-sm);
}
.typing__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--sl-text-secondary);
  animation: typing 1.2s infinite ease-in-out;

  &:nth-child(2) {
    animation-delay: 0.2s;
  }
  &:nth-child(3) {
    animation-delay: 0.4s;
  }
}
@keyframes typing {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-4px);
    opacity: 1;
  }
}
</style>
