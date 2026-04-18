const API_BASE = "http://127.0.0.1:8000";
const statusText = document.getElementById("statusText");
const sessionText = document.getElementById("sessionText");
const partialTranscript = document.getElementById("partialTranscript");
const finalTranscript = document.getElementById("finalTranscript");
const eventsBox = document.getElementById("eventsBox");
const startButton = document.getElementById("startButton");
const stopButton = document.getElementById("stopButton");

let socket = null;
let audioContext = null;
let mediaStream = null;
let sourceNode = null;
let processorNode = null;
let sessionId = null;

function setStatus(value) {
  statusText.textContent = value;
}

function appendEvent(payload) {
  const line = JSON.stringify(payload, null, 2);
  eventsBox.textContent = `${line}\n\n${eventsBox.textContent}`.trim();
}

function downsampleBuffer(buffer, inputSampleRate, outputSampleRate) {
  if (outputSampleRate === inputSampleRate) {
    return buffer;
  }

  const ratio = inputSampleRate / outputSampleRate;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;

  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
    let accumulator = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i += 1) {
      accumulator += buffer[i];
      count += 1;
    }
    result[offsetResult] = accumulator / count;
    offsetResult += 1;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

function floatTo16BitPCM(floatBuffer) {
  const pcm = new Int16Array(floatBuffer.length);
  for (let i = 0; i < floatBuffer.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, floatBuffer[i]));
    pcm[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
  }
  return pcm.buffer;
}

async function startRecording() {
  setStatus("creating session");
  startButton.disabled = true;
  stopButton.disabled = false;
  finalTranscript.textContent = "";
  partialTranscript.textContent = "Listening…";
  eventsBox.textContent = "";

  const response = await fetch(`${API_BASE}/v1/sessions`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Session creation failed: ${response.status}`);
  }

  const session = await response.json();
  sessionId = session.session_id;
  sessionText.textContent = sessionId;

  socket = new WebSocket(session.ws_url);
  socket.binaryType = "arraybuffer";

  socket.onopen = async () => {
    try {
      setStatus("connected");
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioContext = new AudioContext();
      sourceNode = audioContext.createMediaStreamSource(mediaStream);
      processorNode = audioContext.createScriptProcessor(4096, 1, 1);

      processorNode.onaudioprocess = (event) => {
        if (!socket || socket.readyState !== WebSocket.OPEN) {
          return;
        }
        const input = event.inputBuffer.getChannelData(0);
        const downsampled = downsampleBuffer(input, audioContext.sampleRate, 16000);
        const pcmBuffer = floatTo16BitPCM(downsampled);
        socket.send(pcmBuffer);
      };

      sourceNode.connect(processorNode);
      processorNode.connect(audioContext.destination);
    } catch (error) {
      appendEvent({ type: "frontend.error", message: `Microphone setup failed: ${String(error)}` });
      setStatus("mic error");
      await stopRecording();
    }
  };

  socket.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    appendEvent(payload);

    if (payload.type === "transcript.partial") {
      partialTranscript.textContent = payload.text || "Listening…";
      return;
    }

    if (payload.type === "transcript.final") {
      partialTranscript.textContent = "Listening…";
      finalTranscript.textContent += `${payload.text}\n`;
    }

    if (payload.type === "session.error") {
      setStatus("error");
    }

    if (payload.type === "session.completed") {
      setStatus("completed");
    }
  };

  socket.onerror = () => {
    setStatus("socket error");
  };

  socket.onclose = () => {
    setStatus("disconnected");
  };
}

async function stopRecording() {
  stopButton.disabled = true;
  startButton.disabled = false;
  setStatus("stopping");

  if (processorNode) {
    processorNode.disconnect();
    processorNode.onaudioprocess = null;
    processorNode = null;
  }
  if (sourceNode) {
    sourceNode.disconnect();
    sourceNode = null;
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }
  if (audioContext) {
    await audioContext.close();
    audioContext = null;
  }
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.close();
  }
  socket = null;
}

startButton.addEventListener("click", async () => {
  try {
    await startRecording();
  } catch (error) {
    appendEvent({ type: "frontend.error", message: String(error) });
    setStatus("error");
    startButton.disabled = false;
    stopButton.disabled = true;
  }
});

stopButton.addEventListener("click", async () => {
  try {
    await stopRecording();
  } catch (error) {
    appendEvent({ type: "frontend.error", message: String(error) });
    setStatus("error");
  }
});
