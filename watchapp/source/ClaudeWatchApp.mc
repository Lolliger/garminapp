import Toybox.Application;
import Toybox.Lang;
import Toybox.WatchUi;

//! Shows the oldest open Claude Code question from the relay and sends back the chosen option.
class ClaudeWatchApp extends Application.AppBase {

    public function initialize() {
        AppBase.initialize();
    }

    public function getInitialView() as [Views] or [Views, InputDelegates] {
        var view = new $.MainView();
        return [view, new $.MainDelegate(view)];
    }
}
