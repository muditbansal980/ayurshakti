export type Chat = {
  id: string;
  title: string;
};

export type Attachment = {
  id: string;
  name: string;
  size: number;
};

export type SourceCitation = {
  id: string;
  title: string;
  provision: string;
  review_status: string;
  document_id?: string;
  pages?: number[];
  jurisdiction?: string;
};

// Legacy Citation type preserved for compatibility
export type Citation = {
  title?: string;
  provision?: string;
  source_url?: string;
  jurisdiction?: string;
  review_status?: string;
  pdf_pages?: number[];
  parent_pdf_pages?: number[];
};

export type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
  attachments?: Attachment[];
  sources?: SourceCitation[];
  citations?: Citation[];
  status?: "pending" | "generating" | "complete" | "error";
  loadingText?: string;
  mode?: "rag" | "no_context" | "error" | "greeting";
  model?: string;
};
