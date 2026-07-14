export type TaskStatus = 'auto_confirmed' | 'pending' | 'confirmed' | 'rejected';

export interface Task {
  id: string;
  title: string;
  datetime: string;
  end_datetime: string | null;
  location: string | null;
  attendees: string[];
  notes: string | null;
  confidence: number;
  source: string;
  status: TaskStatus;
  created_at: string;
}

export interface ExtractionResult {
  tasks: Task[];
  auto_added: number;
  pending_review: number;
  discarded: number;
}

export interface UploadResponse {
  result: ExtractionResult;
  extracted_text: string;
}
