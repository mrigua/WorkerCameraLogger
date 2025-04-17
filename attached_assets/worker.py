# worker.py
from PyQt6.QtCore import pyqtSignal, QObject, QRunnable # Changed QThread to QRunnable
import logging
import traceback # Import traceback explicitly

class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker task.
    Supported signals are:
    finished: No data
    error: tuple (exctype, value, traceback.format_exc())
    result: object data returned from processing, anything
    progress: int indicating % progress (optional)
    status_update: str message for status updates
    """
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)
    status_update = pyqtSignal(str)

# Note: Inherit from QRunnable, not QThread
class Worker(QRunnable):
    """
    Worker runnable for executing tasks in a QThreadPool.
    Inherits from QRunnable. Passes signals via a WorkerSignals object.
    """
    def __init__(self, function, *args, **kwargs):
        super().__init__()  # Call QRunnable's __init__
        self.function = function
        self.args = args
        self.kwargs = kwargs
        # Create a QObject to hold signals. This is necessary because QRunnable itself isn't a QObject.
        self.signals = WorkerSignals()

        # Add signal connectors to allow the target function to emit signals if needed
        # The target function needs to accept these kwargs ('status_signal', 'progress_signal')
        # if it wants to emit progress/status directly.
        self.kwargs['status_signal'] = self.signals.status_update
        self.kwargs['progress_signal'] = self.signals.progress

    # QRunnable's main method is 'run'
    def run(self):
        """Execute the task."""
        # Note: We don't have direct access to QThread.currentThread().name() easily here
        # Log using the function name for context
        func_name = self.function.__name__
        logging.info(f"Starting task in threadpool: {func_name}")
        try:
            result = self.function(*self.args, **self.kwargs)
        except Exception as e:
            logging.error(f"Error during task {func_name}: {e}", exc_info=True)
            exctype, value = type(e), e
            # Emit error signal. Qt handles thread safety for signal emission.
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            # Emit result signal
            self.signals.result.emit(result)
            logging.info(f"Task finished successfully: {func_name}")
        finally:
            # Emit finished signal
            self.signals.finished.emit()