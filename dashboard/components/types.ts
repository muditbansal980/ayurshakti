export type Chat = {
  id: string;
  title: string;
};

export type Attachment = {
  id: string;
  name: string;
  size: number;
};

export type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
  attachments?: Attachment[];
};
