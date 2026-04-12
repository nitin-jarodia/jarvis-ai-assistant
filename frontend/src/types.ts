export type AgentMode = "auto" | "chat" | "generate_image" | "analyze_image";

export type MessageType = "text" | "image_generation" | "image_analysis";

export interface Chat {
  id: number;
  user_id?: number | null;
  title: string;
  document_file_id?: string | null;
  document_filename?: string | null;
  created_at: string;
  updated_at?: string | null;
  is_active: boolean;
}

export interface Message {
  id: number | string;
  chat_id: number;
  role: "user" | "assistant";
  content: string;
  agent_type?: string | null;
  message_type?: MessageType;
  image_url?: string | null;
  attachment_url?: string | null;
  provider?: string | null;
  message_metadata?: Record<string, unknown> | null;
  created_at?: string;
}

export interface ActiveFile {
  id: string;
  name: string;
  meta: string;
}

export interface PendingImage {
  file: File;
  previewUrl: string;
  name: string;
  size: number;
  type: string;
}

export interface Note {
  id: number;
  title: string;
  content: string;
  created_at: string;
  updated_at?: string | null;
}

export interface HealthResponse {
  status: string;
  ai_service?: { status?: string };
}

export interface SendMessageResponse {
  chat_id: number;
  user_message_id: number;
  assistant_message_id: number;
  reply: string;
  agent_type?: string | null;
  message_type: MessageType;
  image_url?: string | null;
  attachment_url?: string | null;
  metadata?: Record<string, unknown>;
}

export interface ChatStreamStart {
  chat_id: number;
  user_message_id: number;
  message_type: MessageType;
  agent_type?: string | null;
  provider?: string | null;
  model?: string | null;
}

export interface ChatStreamChunk {
  delta: string;
}
