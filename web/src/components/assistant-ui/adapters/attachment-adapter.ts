import {
  SimpleImageAttachmentAdapter,
  CompositeAttachmentAdapter,
  type AttachmentAdapter,
  type PendingAttachment,
  type CompleteAttachment,
  type Attachment,
} from "@assistant-ui/react";

export class SimpleAudioAttachmentAdapter implements AttachmentAdapter {
  public accept = "audio/*, .mp3, .wav, .m4a, .ogg, .aac, .flac";

  public async add(state: { file: File }): Promise<PendingAttachment> {
    return {
      id: crypto.randomUUID(),
      type: "file",
      name: state.file.name,
      contentType: state.file.type || "audio/mpeg",
      file: state.file,
      status: { type: "requires-action", reason: "composer-send" },
    };
  }

  public async send(
    attachment: PendingAttachment,
    options?: { signal?: AbortSignal },
  ): Promise<CompleteAttachment> {
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      if (options?.signal) {
        options.signal.addEventListener("abort", () => {
          reader.abort();
          reject(new Error("Attachment upload aborted"));
        });
      }
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = (e) => reject(e);
      reader.readAsDataURL(attachment.file);
    });

    return {
      ...attachment,
      status: { type: "complete" },
      content: [
        {
          type: "file",
          data: dataUrl,
          mimeType: attachment.file.type || "audio/mpeg",
          filename: attachment.name,
        },
      ],
    };
  }

  public async remove(_attachment: Attachment): Promise<void> {}
}

export const multimodalAttachmentAdapter = new CompositeAttachmentAdapter([
  new SimpleImageAttachmentAdapter(),
  new SimpleAudioAttachmentAdapter(),
]);
