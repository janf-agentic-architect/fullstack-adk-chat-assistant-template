/** @jsxImportSource react */
import {
  ThreadPrimitive,
  MessagePrimitive,
  ComposerPrimitive,
  AttachmentPrimitive,
} from "@assistant-ui/react";

export function Thread() {
  return (
    <ThreadPrimitive.Root className="aui-thread-root">
      <ThreadPrimitive.Viewport className="aui-thread-viewport">
        <ThreadPrimitive.Empty>
          <p className="aui-empty">Hello! How can I help you today?</p>
        </ThreadPrimitive.Empty>

        <ThreadPrimitive.Messages
          components={{
            UserMessage,
            AssistantMessage,
          }}
        />
      </ThreadPrimitive.Viewport>

      <ComposerPrimitive.Root className="aui-composer-root">
        <ComposerPrimitive.Attachments className="aui-composer-attachments-list">
          {() => (
            <AttachmentPrimitive.Root className="aui-attachment-card">
              <AttachmentPrimitive.unstable_Thumb className="aui-attachment-thumb" />
              <div className="aui-attachment-info">
                <AttachmentPrimitive.Name className="aui-attachment-name" />
              </div>
              <AttachmentPrimitive.Remove
                className="aui-attachment-remove"
                title="Remove attachment"
              >
                ✕
              </AttachmentPrimitive.Remove>
            </AttachmentPrimitive.Root>
          )}
        </ComposerPrimitive.Attachments>

        <div className="aui-composer-controls">
          <ComposerPrimitive.AddAttachment
            className="aui-composer-attach"
            title="Attach image or audio"
            aria-label="Attach image or audio"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48" />
            </svg>
          </ComposerPrimitive.AddAttachment>

          <ComposerPrimitive.Input
            placeholder="Type a message or attach images / audio..."
            className="aui-composer-input"
          />
          <ComposerPrimitive.Send className="aui-composer-send">
            Send
          </ComposerPrimitive.Send>
        </div>
      </ComposerPrimitive.Root>
    </ThreadPrimitive.Root>
  );
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="aui-message aui-message-user">
      <MessagePrimitive.Attachments className="aui-message-attachments">
        {({ attachment }) => {
          if (attachment.type === "image") {
            const imagePart = attachment.content?.find((p) => p.type === "image");
            if (imagePart && "image" in imagePart && imagePart.image) {
              return (
                <div key={attachment.id} className="aui-message-attachment-image-container">
                  <img
                    src={(imagePart as any).image}
                    alt={attachment.name}
                    className="aui-attachment-img"
                  />
                </div>
              );
            }
          }

          const filePart = attachment.content?.find(
            (p) => p.type === "file" || p.type === "audio"
          );
          const isAudio =
            attachment.contentType?.startsWith("audio/") ||
            (filePart &&
              "mimeType" in filePart &&
              (filePart as any).mimeType?.startsWith("audio/")) ||
            /\.(mp3|wav|ogg|m4a|aac|flac)$/i.test(attachment.name);

          if (isAudio && filePart && "data" in filePart) {
            return (
              <div key={attachment.id} className="aui-message-attachment-audio-container">
                <div className="aui-audio-header">
                  <span>🎵</span>
                  <span className="aui-audio-name">{attachment.name}</span>
                </div>
                <audio
                  controls
                  src={(filePart as any).data}
                  className="aui-audio-player"
                />
              </div>
            );
          }

          return (
            <div key={attachment.id} className="aui-message-attachment-file">
              📎 <span>{attachment.name}</span>
            </div>
          );
        }}
      </MessagePrimitive.Attachments>
      <MessagePrimitive.Parts />
    </MessagePrimitive.Root>
  );
}

function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="aui-message aui-message-assistant">
      <MessagePrimitive.Parts />
    </MessagePrimitive.Root>
  );
}
