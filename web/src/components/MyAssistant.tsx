/** @jsxImportSource react */
import { AssistantRuntimeProvider } from "@assistant-ui/react";
import {
  useAdkRuntime,
  createAdkStream,
  createAdkSessionAdapter,
} from "@assistant-ui/react-google-adk";
import { Thread } from "@/components/assistant-ui/elements/thread.aui";
import { multimodalAttachmentAdapter } from "@/components/assistant-ui/adapters/attachment-adapter";

const ADK_API_URL = "/api/adk";
const ADK_APP_NAME = "app";
const ADK_USER_ID = "user-1";

const { adapter: sessionAdapter, load } = createAdkSessionAdapter({
  apiUrl: ADK_API_URL,
  appName: ADK_APP_NAME,
  userId: ADK_USER_ID,
});

const ADKstream = createAdkStream({
  api: ADK_API_URL,
  appName: ADK_APP_NAME,
  userId: ADK_USER_ID,
});

export function MyAssistant() {
  const runtime = useAdkRuntime({
    stream: ADKstream,
    sessionAdapter,
    load,
    adapters: {
      attachments: multimodalAttachmentAdapter,
    },
  });
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <Thread />
    </AssistantRuntimeProvider>
  );
}
