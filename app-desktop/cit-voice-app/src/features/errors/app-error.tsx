import { Button } from "@/components/ui/button";
import {
  ErrorActions,
  ErrorDescription,
  ErrorHeader,
  ErrorView,
} from "@/features/errors/error-base";

export default function AppErrorPage() {
  return (
    <ErrorView>
      <ErrorHeader>Giao diện gặp lỗi</ErrorHeader>
      <ErrorDescription>
        Tải lại để tiếp tục. Lịch sử và giọng đã lưu không bị mất.
      </ErrorDescription>
      <ErrorActions>
        <Button onClick={() => window.location.reload()} size="lg">
          Tải lại
        </Button>
      </ErrorActions>
    </ErrorView>
  );
}
