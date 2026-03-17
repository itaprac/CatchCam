import {
  FilesetResolver,
  HandLandmarker,
  PoseLandmarker,
} from "@mediapipe/tasks-vision";

const HAND_MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task";
const POSE_MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task";
const WASM_ROOT = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.9/wasm";

const GAME_DURATION = 60;
const COMBO_TIMEOUT = 1.2;
const SLOW_MO_DURATION = 1.6;

const PHASES = [
  {
    from: 0,
    spawnInterval: 0.58,
    maxObjects: 6,
    speedRange: [185, 285],
    weights: { normal: 79, gold: 10, bomb: 8, slow: 3 },
  },
  {
    from: 20,
    spawnInterval: 0.43,
    maxObjects: 8,
    speedRange: [225, 340],
    weights: { normal: 72, gold: 12, bomb: 11, slow: 5 },
  },
  {
    from: 40,
    spawnInterval: 0.32,
    maxObjects: 10,
    speedRange: [270, 410],
    weights: { normal: 65, gold: 12, bomb: 17, slow: 6 },
  },
];

const KIND_META = {
  normal: { fill: "#2f6df6", outline: "#f7f2e8", glow: "rgba(47,109,246,0.26)", base: 1 },
  gold: { fill: "#ff9f1c", outline: "#f7f2e8", glow: "rgba(255,159,28,0.32)", base: 3 },
  slow: { fill: "#12b886", outline: "#f7f2e8", glow: "rgba(18,184,134,0.28)", base: 2 },
  bomb: { fill: "#ef476f", outline: "#2e0f17", glow: "rgba(239,71,111,0.28)", base: -10 },
};

const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16],
  [13, 17], [17, 18], [18, 19], [19, 20],
  [0, 17],
];

const PALM_INDICES = [0, 5, 9, 13, 17];
const PREVIEW_INDICES = [4, 8, 12, 16, 20];

const POSE_CONNECTIONS = [
  [11, 12],
  [11, 13], [13, 15],
  [12, 14], [14, 16],
  [11, 23], [12, 24],
  [23, 24],
  [23, 25], [25, 27],
  [24, 26], [26, 28],
];

export class OpenDayGame {
  constructor({ video, canvas, onStateChange, onResult }) {
    this.video = video;
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.onStateChange = onStateChange;
    this.onResult = onResult;
    this.handLandmarker = null;
    this.poseLandmarker = null;
    this.stream = null;
    this.lastVideoTime = -1;
    this.lastFrameTime = 0;
    this.animationFrame = 0;
    this.playerName = "";
    this.statusMode = "loading";
    this.statusMessage = "Ladowanie...";
    this.pixelRatio = 1;
    this.renderWidth = 1280;
    this.renderHeight = 720;
    this.resetSessionState();
  }

  async init() {
    const vision = await FilesetResolver.forVisionTasks(WASM_ROOT);

    this.handLandmarker = await HandLandmarker.createFromOptions(vision, {
      baseOptions: { modelAssetPath: HAND_MODEL_URL },
      runningMode: "VIDEO",
      numHands: 2,
      minHandDetectionConfidence: 0.5,
      minHandPresenceConfidence: 0.5,
      minTrackingConfidence: 0.5,
    });

    this.poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
      baseOptions: { modelAssetPath: POSE_MODEL_URL },
      runningMode: "VIDEO",
      numPoses: 1,
      minPoseDetectionConfidence: 0.5,
      minPosePresenceConfidence: 0.5,
      minTrackingConfidence: 0.5,
    });

    this.setStatus("ready", "Podaj imie i kliknij graj.");
  }

  async startCamera() {
    if (this.stream) {
      return;
    }

    this.stream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 1280 },
        height: { ideal: 720 },
        facingMode: "user",
      },
      audio: false,
    });

    this.video.srcObject = this.stream;
    await this.video.play();
    this.resizeCanvas();
    this.lastFrameTime = performance.now();
    this.loop();
  }

  resizeCanvas() {
    const rect = this.canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) {
      return;
    }

    this.pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    this.renderWidth = rect.width;
    this.renderHeight = rect.height;
    this.canvas.width = Math.round(rect.width * this.pixelRatio);
    this.canvas.height = Math.round(rect.height * this.pixelRatio);
  }

  startRound(playerName) {
    this.playerName = playerName.trim() || "Gracz";
    this.resetRound();
    this.mode = "playing";
    this.setStatus("playing", "Runda trwa.");
  }

  resetRound() {
    this.elapsed = 0;
    this.score = 0;
    this.phase = 1;
    this.comboCount = 0;
    this.comboMultiplier = 1;
    this.bestCombo = 0;
    this.lastHitAge = null;
    this.spawnTimer = 0;
    this.slowMoTimer = 0;
    this.objects = [];
    this.effects = [];
    this.stats = { gold: 0, slow: 0, bomb: 0 };
    this.mode = "ready";
  }

  resetSessionState() {
    this.resetRound();
    this.smoothedTouchPoints = [];
    this.previewTouchPoints = [];
    this.handCollisionShapes = [];
    this.poseResult = null;
    this.handResult = null;
  }

  stop() {
    cancelAnimationFrame(this.animationFrame);
    if (this.stream) {
      for (const track of this.stream.getTracks()) {
        track.stop();
      }
      this.stream = null;
    }
    this.video.pause();
  }

  loop = () => {
    this.animationFrame = requestAnimationFrame(this.loop);
    if (!this.video.videoWidth || !this.video.videoHeight) {
      return;
    }

    const now = performance.now();
    const delta = Math.min((now - this.lastFrameTime) / 1000, 0.1);
    this.lastFrameTime = now;

    if (this.video.currentTime !== this.lastVideoTime) {
      this.lastVideoTime = this.video.currentTime;
      this.detect(now);
    }

    this.update(delta);
    this.render();
  };

  detect(timestamp) {
    try {
      this.handResult = this.handLandmarker.detectForVideo(this.video, timestamp);
      this.poseResult = this.poseLandmarker.detectForVideo(this.video, timestamp);
    } catch {
      this.setStatus("error", "Nie udalo sie przetworzyc obrazu z kamery.");
    }
  }

  update(delta) {
    this.handCollisionShapes = this.collectHandShapes();
    const rawPreviewPoints = this.handCollisionShapes.flatMap((shape) => shape.previewPoints);
    this.previewTouchPoints = smoothTouchPoints(this.previewTouchPoints, rawPreviewPoints);
    this.advanceEffects(delta);

    if (this.mode !== "playing") {
      this.emitStatus();
      return;
    }

    this.elapsed = Math.min(GAME_DURATION, this.elapsed + delta);
    this.phase = phaseNumber(this.elapsed);

    if (this.slowMoTimer > 0) {
      this.slowMoTimer = Math.max(0, this.slowMoTimer - delta);
    }

    if (this.comboCount > 0 && this.lastHitAge !== null) {
      this.lastHitAge += delta;
      if (this.lastHitAge > COMBO_TIMEOUT) {
        this.comboCount = 0;
        this.comboMultiplier = 1;
        this.lastHitAge = null;
      }
    }

    this.moveObjects(delta);
    this.collectHits();
    this.spawnObjects(delta);
    this.objects = this.objects.filter((item) => item.y - item.radius <= this.renderHeight);

    if (this.elapsed >= GAME_DURATION) {
      this.finishRound();
      return;
    }

    this.emitStatus();
  }

  finishRound() {
    this.mode = "gameOver";
    this.setStatus("gameOver", "Koniec rundy.");
    this.onResult?.({
      name: this.playerName,
      score: this.score,
      combo: this.bestCombo,
      stats: { ...this.stats },
    });
  }

  moveObjects(delta) {
    const speedScale = this.slowMoTimer > 0 ? 0.78 : 1;
    for (const item of this.objects) {
      item.y += item.speed * speedScale * delta;
    }
  }

  spawnObjects(delta) {
    const phase = getPhase(this.elapsed);
    const spawnInterval = phase.spawnInterval * (this.slowMoTimer > 0 ? 1.12 : 1);
    this.spawnTimer += delta;

    while (
      this.spawnTimer >= spawnInterval &&
      this.objects.length < phase.maxObjects &&
      this.renderWidth > 0 &&
      this.renderHeight > 0
    ) {
      this.spawnTimer -= spawnInterval;
      this.objects.push(this.createObject(phase));
    }
  }

  createObject(phase) {
    const radius = randomBetween(20, 36);
    const kind = pickKind(phase.weights, this.elapsed < 5);
    const [minSpeed, maxSpeed] = phase.speedRange;
    return {
      id: crypto.randomUUID(),
      kind,
      x: randomBetween(radius, this.renderWidth - radius),
      y: -radius,
      radius,
      speed: randomBetween(minSpeed, maxSpeed),
    };
  }

  collectHits() {
    if (!this.handCollisionShapes.length) {
      return;
    }

    const survivors = [];
    for (const item of this.objects) {
      const hit = this.handCollisionShapes.some((shape) => handShapeHitsObject(shape, item));

      if (!hit) {
        survivors.push(item);
        continue;
      }

      this.handleHit(item);
    }

    this.objects = survivors;
  }

  handleHit(item) {
    const meta = KIND_META[item.kind];

    if (item.kind === "bomb") {
      this.score = Math.max(0, this.score - 10);
      this.comboCount = 0;
      this.comboMultiplier = 1;
      this.lastHitAge = null;
      this.stats.bomb += 1;
      this.effects.push({
        type: "flash",
        age: 0,
        duration: 0.18,
        color: "rgba(239,71,111,0.26)",
      });
      this.effects.push({
        type: "text",
        age: 0,
        duration: 0.75,
        x: item.x,
        y: item.y,
        text: "-10",
        color: meta.fill,
        scale: 0.9,
      });
      this.effects.push({
        type: "ring",
        age: 0,
        duration: 0.32,
        x: item.x,
        y: item.y,
        color: meta.fill,
      });
      return;
    }

    this.comboCount += 1;
    this.comboMultiplier = comboMultiplier(this.comboCount);
    this.bestCombo = Math.max(this.bestCombo, this.comboCount);
    this.lastHitAge = 0;

    const gained = meta.base * this.comboMultiplier;
    this.score += gained;

    if (item.kind === "gold") {
      this.stats.gold += 1;
    }

    if (item.kind === "slow") {
      this.stats.slow += 1;
      this.slowMoTimer = SLOW_MO_DURATION;
      this.effects.push({
        type: "flash",
        age: 0,
        duration: 0.16,
        color: "rgba(18,184,134,0.14)",
      });
    }

    this.effects.push({
      type: "ring",
      age: 0,
      duration: 0.3,
      x: item.x,
      y: item.y,
      color: meta.fill,
    });
    this.effects.push({
      type: "text",
      age: 0,
      duration: 0.75,
      x: item.x,
      y: item.y,
      text: `+${gained}`,
      color: meta.fill,
      scale: 0.95,
    });

    if (this.comboMultiplier > 1) {
      this.effects.push({
        type: "text",
        age: 0,
        duration: 0.65,
        x: item.x,
        y: item.y - 28,
        text: `x${this.comboMultiplier}`,
        color: "#f7f2e8",
        scale: 0.72,
      });
    }
  }

  advanceEffects(delta) {
    this.effects = this.effects.filter((effect) => {
      effect.age += delta;
      return effect.age < effect.duration;
    });
  }

  collectHandShapes() {
    const hands = this.handResult?.landmarks || [];
    return hands.map((hand) => {
      const points = hand.map((point) => this.mapNormalizedPoint(point.x, point.y));
      const palm = PALM_INDICES.map((index) => points[index]);
      const palmCenter = averagePoint(palm);
      const previewPoints = [palmCenter, ...PREVIEW_INDICES.map((index) => points[index])];
      const segments = HAND_CONNECTIONS.map(([from, to]) => [points[from], points[to]]);

      return {
        points,
        palm,
        palmCenter,
        previewPoints,
        segments,
      };
    });
  }

  mapNormalizedPoint(x, y) {
    const layout = this.getVideoLayout();
    const sourceX = x * this.video.videoWidth;
    const sourceY = y * this.video.videoHeight;
    const fittedX = (sourceX - layout.sx) * (this.renderWidth / layout.sw);
    const fittedY = (sourceY - layout.sy) * (this.renderHeight / layout.sh);

    return {
      x: this.renderWidth - fittedX,
      y: fittedY,
    };
  }

  getVideoLayout() {
    const sourceWidth = this.video.videoWidth || 1280;
    const sourceHeight = this.video.videoHeight || 720;
    const sourceRatio = sourceWidth / sourceHeight;
    const targetRatio = this.renderWidth / this.renderHeight;

    if (targetRatio > sourceRatio) {
      const sh = sourceWidth / targetRatio;
      return {
        sx: 0,
        sy: (sourceHeight - sh) / 2,
        sw: sourceWidth,
        sh,
      };
    }

    const sw = sourceHeight * targetRatio;
    return {
      sx: (sourceWidth - sw) / 2,
      sy: 0,
      sw,
      sh: sourceHeight,
    };
  }

  setStatus(mode, message) {
    this.statusMode = mode;
    this.statusMessage = message;
    this.emitStatus();
  }

  emitStatus() {
    this.onStateChange?.({
      mode: this.statusMode,
      message: this.statusMessage,
      playerName: this.playerName,
      score: this.score,
      combo: this.comboCount,
      multiplier: this.comboMultiplier,
      bestCombo: this.bestCombo,
      phase: this.phase,
      timeLeft: Math.max(0, Math.ceil(GAME_DURATION - this.elapsed)),
      slowMoTimer: this.slowMoTimer,
      isPlaying: this.mode === "playing",
    });
  }

  render() {
    const ctx = this.ctx;
    const width = this.renderWidth;
    const height = this.renderHeight;
    const layout = this.getVideoLayout();

    ctx.setTransform(this.pixelRatio, 0, 0, this.pixelRatio, 0, 0);
    ctx.clearRect(0, 0, width, height);

    ctx.save();
    ctx.translate(width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(this.video, layout.sx, layout.sy, layout.sw, layout.sh, 0, 0, width, height);
    ctx.restore();

    const vignette = ctx.createLinearGradient(0, 0, 0, height);
    vignette.addColorStop(0, "rgba(6,8,12,0.06)");
    vignette.addColorStop(1, "rgba(6,8,12,0.34)");
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, width, height);

    this.drawDetectionMagic();
    this.drawObjects();
    this.drawEffects();
    this.drawTouchPoints();
    this.drawHud();
  }

  drawDetectionMagic() {
    const ctx = this.ctx;
    const pose = this.poseResult?.landmarks?.[0];

    if (pose?.length) {
      ctx.save();
      ctx.strokeStyle = "rgba(115, 208, 255, 0.42)";
      ctx.lineWidth = 3;
      for (const [from, to] of POSE_CONNECTIONS) {
        const first = pose[from];
        const second = pose[to];
        if (!first || !second) {
          continue;
        }
        const visibility = Math.min(first.visibility ?? 0, second.visibility ?? 0);
        if (visibility < 0.35) {
          continue;
        }
        const start = this.mapNormalizedPoint(first.x, first.y);
        const end = this.mapNormalizedPoint(second.x, second.y);
        ctx.globalAlpha = visibility;
        ctx.beginPath();
        ctx.moveTo(start.x, start.y);
        ctx.lineTo(end.x, end.y);
        ctx.stroke();
      }

      ctx.fillStyle = "rgba(194, 240, 255, 0.78)";
      for (const index of [11, 12, 13, 14, 15, 16, 23, 24]) {
        const point = pose[index];
        if (!point || (point.visibility ?? 0) < 0.35) {
          continue;
        }
        const mapped = this.mapNormalizedPoint(point.x, point.y);
        ctx.globalAlpha = point.visibility ?? 1;
        ctx.beginPath();
        ctx.arc(mapped.x, mapped.y, 5, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }

    const hands = this.handResult?.landmarks || [];
    for (const hand of hands) {
      ctx.save();
      ctx.strokeStyle = "rgba(255, 232, 186, 0.72)";
      ctx.lineWidth = 2.5;
      for (const [from, to] of HAND_CONNECTIONS) {
        const start = this.mapNormalizedPoint(hand[from].x, hand[from].y);
        const end = this.mapNormalizedPoint(hand[to].x, hand[to].y);
        ctx.beginPath();
        ctx.moveTo(start.x, start.y);
        ctx.lineTo(end.x, end.y);
        ctx.stroke();
      }

      ctx.fillStyle = "rgba(255, 190, 95, 0.92)";
      for (const point of hand) {
        const mapped = this.mapNormalizedPoint(point.x, point.y);
        ctx.beginPath();
        ctx.arc(mapped.x, mapped.y, 3.5, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }
  }

  drawObjects() {
    const ctx = this.ctx;
    for (const item of this.objects) {
      const meta = KIND_META[item.kind];
      ctx.save();
      ctx.fillStyle = meta.glow;
      ctx.beginPath();
      ctx.arc(item.x, item.y, item.radius + 14, 0, Math.PI * 2);
      ctx.fill();

      if (item.kind === "bomb") {
        ctx.fillStyle = meta.outline;
        ctx.beginPath();
        ctx.arc(item.x, item.y, item.radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = meta.fill;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(item.x, item.y, item.radius + 1, 0, Math.PI * 2);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(item.x - item.radius / 2, item.y - item.radius / 2);
        ctx.lineTo(item.x + item.radius / 2, item.y + item.radius / 2);
        ctx.moveTo(item.x - item.radius / 2, item.y + item.radius / 2);
        ctx.lineTo(item.x + item.radius / 2, item.y - item.radius / 2);
        ctx.stroke();
      } else {
        ctx.fillStyle = meta.fill;
        ctx.beginPath();
        ctx.arc(item.x, item.y, item.radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = meta.outline;
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.fillStyle = "rgba(255,255,255,0.72)";
        ctx.beginPath();
        ctx.arc(
          item.x - item.radius * 0.32,
          item.y - item.radius * 0.32,
          Math.max(4, item.radius / 5),
          0,
          Math.PI * 2,
        );
        ctx.fill();
      }
      ctx.restore();
    }
  }

  drawEffects() {
    const ctx = this.ctx;
    for (const effect of this.effects) {
      const progress = effect.age / effect.duration;
      if (effect.type === "flash") {
        ctx.fillStyle = effect.color;
        ctx.fillRect(0, 0, this.renderWidth, this.renderHeight);
      } else if (effect.type === "ring") {
        ctx.save();
        ctx.globalAlpha = 1 - progress;
        ctx.strokeStyle = effect.color;
        ctx.lineWidth = Math.max(1, 4 * (1 - progress));
        ctx.beginPath();
        ctx.arc(effect.x, effect.y, 16 + progress * 48, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      } else if (effect.type === "text") {
        ctx.save();
        ctx.fillStyle = effect.color;
        ctx.font = `${Math.round(14 + effect.scale * 14)}px "Syne", sans-serif`;
        ctx.textAlign = "center";
        ctx.fillText(effect.text, effect.x, effect.y - progress * 40);
        ctx.restore();
      }
    }
  }

  drawTouchPoints() {
    const ctx = this.ctx;
    ctx.save();
    for (const shape of this.handCollisionShapes) {
      ctx.fillStyle = "rgba(255,255,255,0.08)";
      ctx.strokeStyle = "rgba(255,255,255,0.22)";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(shape.palm[0].x, shape.palm[0].y);
      for (const point of shape.palm.slice(1)) {
        ctx.lineTo(point.x, point.y);
      }
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    }

    for (const point of this.previewTouchPoints) {
      ctx.fillStyle = "rgba(255,255,255,0.18)";
      ctx.beginPath();
      ctx.arc(point.x, point.y, 12, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "rgba(255,255,255,0.64)";
      ctx.beginPath();
      ctx.arc(point.x, point.y, 5, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  drawHud() {
    const ctx = this.ctx;
    const width = this.renderWidth;
    const timeLeft = Math.max(0, Math.ceil(GAME_DURATION - this.elapsed));
    const safeTop = 30;
    const leftX = 26;
    const rightX = width - 182;

    ctx.save();
    drawRoundedPanel(ctx, leftX, safeTop, 160, 54, "rgba(10, 12, 18, 0.6)");
    drawRoundedPanel(ctx, rightX, safeTop, 156, 54, "rgba(10, 12, 18, 0.6)");

    ctx.fillStyle = "#f7f2e8";
    drawHudText(ctx, `Wynik ${this.score}`, leftX + 16, safeTop + 35, 22, "left");
    drawHudText(ctx, `${timeLeft} s`, rightX + 140, safeTop + 35, 22, "right");

    if (this.playerName) {
      drawRoundedPanel(ctx, leftX, safeTop + 66, 220, 40, "rgba(10, 12, 18, 0.44)");
      drawHudText(ctx, this.playerName, leftX + 16, safeTop + 93, 17, "left", "rgba(247, 242, 232, 0.88)");
    }

    if (this.comboCount >= 2) {
      const comboText = `Combo x${this.comboMultiplier}`;
      const boxWidth = Math.max(164, ctx.measureText(comboText).width + 42);
      drawRoundedPanel(ctx, width / 2 - boxWidth / 2, safeTop, boxWidth, 54, "rgba(255, 159, 28, 0.24)");
      drawHudText(ctx, comboText, width / 2, safeTop + 35, 22, "center", "#ffd48d");
    }

    if (this.slowMoTimer > 0) {
      drawRoundedPanel(ctx, width / 2 - 92, safeTop + 66, 184, 40, "rgba(18, 184, 134, 0.24)");
      drawHudText(ctx, "Slow-mo", width / 2, safeTop + 93, 17, "center", "#b8f5e0");
    }

    drawPhaseBar(ctx, width, this.elapsed, this.phase, safeTop + 118);
    ctx.restore();
  }
}

function randomBetween(min, max) {
  return min + Math.random() * (max - min);
}

function distance(x1, y1, x2, y2) {
  return Math.hypot(x1 - x2, y1 - y2);
}

function comboMultiplier(count) {
  if (count >= 10) {
    return 4;
  }
  if (count >= 6) {
    return 3;
  }
  if (count >= 3) {
    return 2;
  }
  return 1;
}

function getPhase(elapsed) {
  if (elapsed >= 40) {
    return PHASES[2];
  }
  if (elapsed >= 20) {
    return PHASES[1];
  }
  return PHASES[0];
}

function phaseNumber(elapsed) {
  if (elapsed >= 40) {
    return 3;
  }
  if (elapsed >= 20) {
    return 2;
  }
  return 1;
}

function pickKind(weights, blockBomb) {
  const entries = Object.entries(weights).filter(([kind]) => !(blockBomb && kind === "bomb"));
  const total = entries.reduce((sum, [, value]) => sum + value, 0);
  const roll = Math.random() * total;
  let cursor = 0;
  for (const [kind, value] of entries) {
    cursor += value;
    if (roll <= cursor) {
      return kind;
    }
  }
  return "normal";
}

function smoothTouchPoints(previous, current) {
  if (!current.length) {
    return [];
  }
  if (!previous.length || previous.length !== current.length) {
    return current;
  }

  return current.map((point, index) => ({
    x: previous[index].x * 0.35 + point.x * 0.65,
    y: previous[index].y * 0.35 + point.y * 0.65,
  }));
}

function handShapeHitsObject(shape, item) {
  const pointPadding = item.kind === "bomb" ? 22 : 30;
  const segmentPadding = item.kind === "bomb" ? 18 : 26;
  const centerPadding = item.kind === "bomb" ? 10 : 16;

  if (
    shape.points.some(
      (point) => distance(point.x, point.y, item.x, item.y) <= item.radius + pointPadding,
    )
  ) {
    return true;
  }

  if (
    shape.segments.some(
      ([start, end]) =>
        pointToSegmentDistance(item.x, item.y, start.x, start.y, end.x, end.y) <=
        item.radius + segmentPadding,
    )
  ) {
    return true;
  }

  const palmRadius =
    shape.palm.reduce((sum, point) => sum + distance(point.x, point.y, shape.palmCenter.x, shape.palmCenter.y), 0) /
    Math.max(shape.palm.length, 1);

  if (distance(item.x, item.y, shape.palmCenter.x, shape.palmCenter.y) <= item.radius + palmRadius + centerPadding) {
    return true;
  }

  return pointInPolygon({ x: item.x, y: item.y }, shape.palm);
}

function averagePoint(points) {
  const sum = points.reduce(
    (acc, point) => ({
      x: acc.x + point.x,
      y: acc.y + point.y,
    }),
    { x: 0, y: 0 },
  );

  return {
    x: sum.x / Math.max(points.length, 1),
    y: sum.y / Math.max(points.length, 1),
  };
}

function pointToSegmentDistance(px, py, x1, y1, x2, y2) {
  const dx = x2 - x1;
  const dy = y2 - y1;

  if (dx === 0 && dy === 0) {
    return distance(px, py, x1, y1);
  }

  const t = Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)));
  const projectedX = x1 + t * dx;
  const projectedY = y1 + t * dy;
  return distance(px, py, projectedX, projectedY);
}

function pointInPolygon(point, polygon) {
  let inside = false;

  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].x;
    const yi = polygon[i].y;
    const xj = polygon[j].x;
    const yj = polygon[j].y;

    const intersects =
      yi > point.y !== yj > point.y &&
      point.x < ((xj - xi) * (point.y - yi)) / ((yj - yi) || 0.00001) + xi;

    if (intersects) {
      inside = !inside;
    }
  }

  return inside;
}

function drawRoundedPanel(ctx, x, y, width, height, fill) {
  ctx.fillStyle = fill;
  ctx.beginPath();
  ctx.moveTo(x + 18, y);
  ctx.lineTo(x + width - 18, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + 18);
  ctx.lineTo(x + width, y + height - 18);
  ctx.quadraticCurveTo(x + width, y + height, x + width - 18, y + height);
  ctx.lineTo(x + 18, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - 18);
  ctx.lineTo(x, y + 18);
  ctx.quadraticCurveTo(x, y, x + 18, y);
  ctx.closePath();
  ctx.fill();
}

function drawHudText(ctx, text, x, y, size, align, color = "#f7f2e8") {
  ctx.textAlign = align;
  ctx.font = `700 ${size}px "Instrument Sans", sans-serif`;
  ctx.fillStyle = "rgba(8, 10, 16, 0.9)";
  ctx.fillText(text, x, y + 1);
  ctx.fillStyle = color;
  ctx.fillText(text, x, y);
}

function drawPhaseBar(ctx, canvasWidth, elapsed, phase, y) {
  const width = Math.min(420, canvasWidth - 52);
  const x = (canvasWidth - width) / 2;
  const progress = elapsed / GAME_DURATION;
  const fill = phase === 3 ? "#ef476f" : phase === 2 ? "#ff9f1c" : "#2f6df6";

  drawRoundedPanel(ctx, x, y, width, 12, "rgba(10, 12, 18, 0.36)");
  drawRoundedPanel(ctx, x, y, Math.max(20, width * progress), 12, fill);
}
