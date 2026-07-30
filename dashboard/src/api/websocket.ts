import type { WsMessage } from "../types";

type Handler = (msg: WsMessage) => void;

export class WsClient {
  private ws: WebSocket | null = null;
  private handlers: Handler[] = [];
  private reconnectDelay = 2000;
  private stopped = false;

  connect() {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${window.location.host}/ws`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log("WS connected");
      this.reconnectDelay = 2000;
    };

    this.ws.onmessage = (evt) => {
      try {
        const msg: WsMessage = JSON.parse(evt.data);
        this.handlers.forEach((h) => h(msg));
      } catch {
        console.warn("WS parse error");
      }
    };

    this.ws.onclose = () => {
      if (!this.stopped) {
        console.log(`WS closed, reconnecting in ${this.reconnectDelay}ms`);
        setTimeout(() => this.connect(), this.reconnectDelay);
        this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, 30000);
      }
    };

    this.ws.onerror = (err) => {
      console.error("WS error", err);
    };
  }

  onMessage(handler: Handler) {
    this.handlers.push(handler);
    return () => {
      this.handlers = this.handlers.filter((h) => h !== handler);
    };
  }

  disconnect() {
    this.stopped = true;
    this.ws?.close();
  }
}

export const wsClient = new WsClient();
