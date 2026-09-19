// Synthetic UI coverage compiled into the existing native test driver, never the app.
#include "tests/test_support.h"
#include "ui/main_window.h"
#include "ui/workbench.h"
#include "ui/workspace_files_panel.h"
#include <QDir>
#include <QFile>
#include <QFileDialog>
#include <QFontDatabase>
#include <QDockWidget>
#include <QLabel>
#include <QListWidget>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QSettings>
#include <QTemporaryDir>
#include <QTimer>
#include <QTextBrowser>
#include <QElapsedTimer>
#include <QScrollBar>
#include <QTextDocument>
#include <QToolButton>
#include <QPointer>
#include <gtest/gtest.h>

TEST(AIBenchieCanvasUi, StreamingRefreshCostDiagnostic)
{
    nullxoid::tests::ensureApplication();
    QTemporaryDir temporary;
    ASSERT_TRUE(temporary.isValid());
    QCoreApplication::setOrganizationName("AIBenchie");
    QCoreApplication::setApplicationName("UiTiming-" + QString::number(QCoreApplication::applicationPid()));
    QSettings::setDefaultFormat(QSettings::IniFormat);
    QSettings::setPath(QSettings::IniFormat, QSettings::UserScope, temporary.path());
    ASSERT_GE(QFontDatabase::addApplicationFont("C:/Windows/Fonts/segoeui.ttf"), 0);
    nullxoid::MainWindow window;
    window.resize(1100, 800);
    window.show();
    QCoreApplication::processEvents();
    auto *history = window.findChild<QListWidget *>("historyList");
    auto *chat = window.findChild<QTextBrowser *>("chatView");
    ASSERT_TRUE(history && chat);
    int resets = 0;
    QObject::connect(history->model(), &QAbstractItemModel::modelReset, &window, [&] { ++resets; });
    for (const int count : {2, 10, 40, 160}) {
        nullxoid::ChatSession session;
        session.id = "synthetic-ui-latency";
        for (int i = 0; i < count; ++i) {
            nullxoid::ChatMessage message;
            message.role = i % 2 ? nullxoid::MessageRole::Assistant : nullxoid::MessageRole::User;
            message.content = QString("Disposable timing text. ").repeated(20);
            session.messages.push_back(message);
        }
        session.messages.back().state = nullxoid::MessageState::Streaming;
        window.setChatSession(session);
        resets = 0;
        QElapsedTimer elapsed; elapsed.start();
        bool drained = false;
        // Match Bootstrap's stream-only path; no live account or model.
        for (int chunk = 0; chunk < 30; ++chunk) {
            session.messages.back().content += " next";
            QMetaObject::invokeMethod(&window, [&window, session] {
                window.queueStreamingSession(session);
            }, Qt::QueuedConnection);
        }
        QMetaObject::invokeMethod(&window, [&] { drained = true; }, Qt::QueuedConnection);
        ASSERT_TRUE(nullxoid::tests::waitUntil([&] { return drained; }, 15000));
        ASSERT_TRUE(nullxoid::tests::waitUntil([&] {
            return chat->toPlainText().simplified().contains(session.messages.back().content.simplified());
        }));
        RecordProperty("messages_" + std::to_string(count) + "_burst_ms", elapsed.elapsed());
        RecordProperty("messages_" + std::to_string(count) + "_history_resets", resets);
        EXPECT_EQ(resets, 0);
        // QTextDocument collapses adjacent HTML whitespace when displaying text.
        EXPECT_TRUE(chat->toPlainText().simplified().contains(
            session.messages.back().content.simplified()));
    }
}

TEST(AIBenchieCanvasUi, StreamingAppendsWithoutReplacingEarlierMessagesOrResettingPanels)
{
    nullxoid::tests::ensureApplication();
    nullxoid::MainWindow window;
    window.resize(1100, 800);
    window.show();
    nullxoid::ChatSession session;
    session.id = "disposable-stream";
    nullxoid::ChatMessage user;
    user.content = "Keep this earlier message";
    nullxoid::ChatMessage assistant;
    assistant.role = nullxoid::MessageRole::Assistant;
    assistant.state = nullxoid::MessageState::Streaming;
    session.messages = {user, assistant};
    window.setChatSession(session);
    auto *chat = window.findChild<QTextBrowser *>("chatView");
    auto *history = window.findChild<QListWidget *>("historyList");
    int resets = 0, changed = 0, earliestChange = 1000000;
    QObject::connect(history->model(), &QAbstractItemModel::modelReset, &window, [&] { ++resets; });
    QObject::connect(chat->document(), &QTextDocument::contentsChange, &window,
        [&](int position, int, int) { ++changed; earliestChange = qMin(earliestChange, position); });
    const auto earlierEnd = chat->document()->find(user.content).selectionEnd();
    for (const auto &part : {QString("Hello"), QString(" <tag>&\n  spaced"), QString("\nFinal line")}) {
        session.messages.back().content += part;
        window.queueStreamingSession(session);
        ASSERT_TRUE(nullxoid::tests::waitUntil([&] {
            return chat->toPlainText().simplified().contains(session.messages.back().content.simplified());
        }));
    }
    EXPECT_EQ(changed, 3) << "One text edit per displayed batch, without a document replacement";
    EXPECT_GT(earliestChange, earlierEnd);
    EXPECT_EQ(resets, 0);
    EXPECT_TRUE(chat->toPlainText().contains("<tag>&"));
    EXPECT_TRUE(chat->toPlainText().contains(user.content));
}

TEST(AIBenchieCanvasUi, StreamingTerminalUpdatesDiscardPendingChunksAndOldChats)
{
    nullxoid::tests::ensureApplication();
    nullxoid::MainWindow window;
    auto *chat = window.findChild<QTextBrowser *>("chatView");
    nullxoid::ChatSession session;
    nullxoid::ChatMessage assistant;
    assistant.role = nullxoid::MessageRole::Assistant;
    assistant.state = nullxoid::MessageState::Streaming;
    session.messages.push_back(assistant);
    window.setChatSession(session);
    auto pending = session;
    pending.messages.back().content = "queued unfinished";
    window.queueStreamingSession(pending);
    session.messages.back().state = nullxoid::MessageState::Completed;
    session.messages.back().content = "Final verified text";
    window.setChatSession(session);
    window.queueStreamingSession(pending);
    QTest::qWait(40);
    EXPECT_TRUE(chat->toPlainText().contains("Final verified text"));
    EXPECT_FALSE(chat->toPlainText().contains("queued unfinished"));

    session.messages.back().state = nullxoid::MessageState::Streaming;
    window.setChatSession(session);
    window.queueStreamingSession(pending);
    nullxoid::ChatSession replacement;
    replacement.messages.push_back({.content = "Different chat"});
    window.setChatSession(replacement);
    window.queueStreamingSession(pending);
    QTest::qWait(40);
    EXPECT_TRUE(chat->toPlainText().contains("Different chat"));
    EXPECT_FALSE(chat->toPlainText().contains("queued unfinished"));

    for (const auto state : {nullxoid::MessageState::Cancelled, nullxoid::MessageState::Failed}) {
        session.messages.back().state = nullxoid::MessageState::Streaming;
        window.setChatSession(session);
        window.queueStreamingSession(pending);
        session.messages.back().state = state;
        session.messages.back().content = "Stopped reply";
        window.setChatSession(session);
        QTest::qWait(40);
        EXPECT_TRUE(chat->toPlainText().contains("Stopped reply"));
        EXPECT_FALSE(chat->toPlainText().contains("queued unfinished"));
    }
}

TEST(AIBenchieCanvasUi, StreamingKeepsScrollPositionAcrossBatchesAndSkinChanges)
{
    nullxoid::tests::ensureApplication();
    nullxoid::MainWindow window;
    window.resize(1000, 700);
    window.show();
    nullxoid::ChatSession session;
    nullxoid::ChatMessage message;
    message.content = QString("Earlier message\n").repeated(100);
    session.messages.push_back(message);
    message.id = QUuid::createUuid();
    message.role = nullxoid::MessageRole::Assistant;
    message.state = nullxoid::MessageState::Streaming;
    message.content = "First word";
    session.messages.push_back(message);
    window.setChatSession(session);
    auto *chat = window.findChild<QTextBrowser *>("chatView");
    auto *scroll = chat->verticalScrollBar();
    ASSERT_GT(scroll->maximum(), 50);
    scroll->setValue(10);
    window.workbench().setSkin(nullxoid::Skin::builtin("high-contrast"));
    for (int i = 0; i < 30; ++i) {
        session.messages.back().content += " next";
        window.queueStreamingSession(session);
    }
    ASSERT_TRUE(nullxoid::tests::waitUntil([&] { return chat->toPlainText().contains(session.messages.back().content); }));
    EXPECT_EQ(scroll->value(), 10);
    session.messages.back().state = nullxoid::MessageState::Completed;
    window.setChatSession(session);
    EXPECT_EQ(scroll->value(), 10);
}

TEST(AIBenchieCanvasUi, FloatingGroupDockButtonReturnsPanelAndPreservesDraft)
{
    nullxoid::tests::ensureApplication();
    nullxoid::MainWindow window;
    window.resize(1100, 800);
    window.move(0, 0);
    window.show();
    auto *conversation = window.findChild<QDockWidget *>("conversationDock");
    auto *context = window.findChild<QDockWidget *>("rightPanelDock");
    auto *draft = window.findChild<QPlainTextEdit *>("inputEdit");
    draft->setPlainText("Keep this unsent draft");
    window.tabifyDockWidget(conversation, context);
    context->show();
    conversation->show();
    conversation->raise();
    QTest::qWait(50);
    const auto start = conversation->titleBarWidget()->geometry().center();
    const auto finish = start + QPoint(1200, -150);
    QTest::mousePress(conversation, Qt::LeftButton, Qt::NoModifier, start);
    QTest::mouseMove(conversation, finish, 30);
    QTest::mouseRelease(conversation, Qt::LeftButton, Qt::NoModifier, finish);
    QTest::qWait(250);
    QPointer<QWidget> group = conversation->window();
    ASSERT_TRUE(group && group->inherits("QDockWidgetGroupWindow")) << group->metaObject()->className();
    ASSERT_EQ(context->window(), group.data());
    auto *toggle = conversation->findChild<QToolButton *>("dockToggle_conversationDock");
    ASSERT_NE(toggle, nullptr);
    EXPECT_EQ(toggle->property("dockAction").toString(), "dock");
    toggle->click();
    QTest::qWait(250);
    EXPECT_EQ(conversation->window(), &window);
    EXPECT_TRUE(conversation->isVisible());
    EXPECT_EQ(draft->toPlainText(), "Keep this unsent draft");
    context->findChild<QToolButton *>("dockToggle_rightPanelDock")->click();
    QTest::qWait(250);
    EXPECT_EQ(context->window(), &window);
    EXPECT_TRUE(!group || !group->isVisible());
    for (auto *child : window.findChildren<QWidget *>()) {
        if (!child->inherits("QDockWidgetGroupWindow") || !child->isVisible()) continue;
        bool populated = false;
        for (auto *dock : child->findChildren<QDockWidget *>())
            populated = populated || (dock->window() == child && !dock->isHidden());
        EXPECT_TRUE(populated) << "No visible empty floating group may remain";
    }
}

TEST(AIBenchieCanvasUi, RenderingDoesNotResubmitSelection)
{
    nullxoid::tests::ensureApplication();
    nullxoid::MainWindow window;
    int selections = 0;
    window.setSelectCanvasFileHandler([&](const QString &) { ++selections; });
    nullxoid::CanvasState state;
    state.activeFileId = "first";
    state.files = {{"first", "first.txt", {}}, {"second", "second.txt", {}}};
    window.setCanvasState(state);
    window.setCanvasState(state);
    EXPECT_EQ(selections, 0) << "Rendering must not feed selection back into the controller";
    auto *list = window.findChild<QListWidget *>("canvasFilesList");
    ASSERT_NE(list, nullptr);
    selections = 0;
    list->setCurrentRow(1);
    EXPECT_EQ(selections, 1) << "A real selection still reaches the controller";
}

TEST(AIBenchieCanvasUi, SavedDocumentControlsAndVerifiedSaveSignal)
{
    nullxoid::tests::ensureApplication();
    QTemporaryDir temporary;
    ASSERT_TRUE(temporary.isValid());
    QCoreApplication::setOrganizationName("AIBenchie");
    QCoreApplication::setApplicationName("Canvas-" + QString::number(QCoreApplication::applicationPid()));
    QSettings::setDefaultFormat(QSettings::IniFormat);
    QSettings::setPath(QSettings::IniFormat, QSettings::UserScope, temporary.path());
    QCoreApplication::setAttribute(Qt::AA_DontUseNativeDialogs);
    // The offscreen Windows platform does not enumerate installed fonts itself.
    ASSERT_GE(QFontDatabase::addApplicationFont("C:/Windows/Fonts/segoeui.ttf"), 0);
    ASSERT_GE(QFontDatabase::addApplicationFont("C:/Windows/Fonts/bahnschrift.ttf"), 0);

    nullxoid::CanvasState state;
    state.open = true;
    state.activeFileId = "generated";
    state.files.push_back({"generated", "Generated document.txt", "Generated inside Canvas\n"});
    nullxoid::MainWindow window;
    window.setUpdateCanvasContentHandler([&](const QString &id, const QString &text) {
        for (auto &file : state.files) if (file.id == id) file.content = text;
        window.setCanvasState(state);
    });
    window.setCreateCanvasFileHandler([&](const QString &name) {
        state.activeFileId = "reopened";
        state.files.push_back({state.activeFileId, name, {}});
        window.setCanvasState(state);
    });
    window.setDeleteCanvasFileHandler([&](const QString &) {
        state.files.clear(); state.activeFileId.clear(); window.setCanvasState(state);
    });
    window.setCanvasSnapshotHandler([&] { return state; });
    window.setCanvasState(state);
    window.show();
    QCoreApplication::processEvents();
    auto *save = window.findChild<QPushButton *>("canvasSaveButton");
    auto *open = window.findChild<QPushButton *>("canvasOpenButton");
    auto *bridge = window.findChild<QPushButton *>("canvasBridgeButton");
    auto *editor = window.findChild<QPlainTextEdit *>("canvasEditor");
    auto *panel = window.findChild<nullxoid::WorkspaceFilesPanel *>();
    auto *status = window.findChild<QLabel *>("canvasStatusLabel");
    ASSERT_TRUE(save && open && bridge && editor && panel && status);
    ASSERT_TRUE(save->isVisible() && open->isVisible() && bridge->isVisible());
    const auto path = temporary.filePath("generated.txt");
    const auto chooseFile = [&](QPushButton *button) {
        bool chosen = false;
        QTimer picker;
        QObject::connect(&picker, &QTimer::timeout, &window, [&] {
            if (auto *dialog = window.findChild<QFileDialog *>()) {
                picker.stop(); dialog->selectFile(path); chosen = true;
                QMetaObject::invokeMethod(dialog, "accept", Qt::DirectConnection);
            }
        });
        QTimer watchdog;
        watchdog.setSingleShot(true);
        QObject::connect(&watchdog, &QTimer::timeout, &window, [&] {
            if (auto *dialog = window.findChild<QFileDialog *>()) dialog->reject();
        });
        picker.start(10); watchdog.start(5000);
        button->click();
        return chosen;
    };
    ASSERT_TRUE(chooseFile(save));
    QByteArray bytes; QString error;
    ASSERT_TRUE(panel->access().readFile(path, bytes, error)) << error.toStdString();
    EXPECT_EQ(bytes, "Generated inside Canvas\n");
    EXPECT_TRUE(status->text().contains("Saved locally"));
    EXPECT_FALSE(panel->agentSelection().isEmpty());
    window.findChild<QPushButton *>("canvasDeleteButton")->click();
    EXPECT_TRUE(QFile::exists(path));
    EXPECT_FALSE(panel->access().permits(path));
    ASSERT_TRUE(chooseFile(open));
    EXPECT_EQ(editor->toPlainText(), "Generated inside Canvas\n");

    // The encrypted listener's completion uses this same panel notification.
    ASSERT_TRUE(panel->access().saveFile(path, bytes, "Verified Bridge save\n", error)) << error.toStdString();
    panel->reloadSavedFile(path);
    EXPECT_EQ(editor->toPlainText(), "Verified Bridge save\n");
    EXPECT_EQ(state.files.back().content, "Verified Bridge save\n");
    editor->setPlainText("Local Canvas edit\n");
    save->click();
    ASSERT_TRUE(panel->access().readFile(path, bytes, error)) << error.toStdString();
    EXPECT_EQ(bytes, "Local Canvas edit\n");
    EXPECT_FALSE(panel->hasUnsavedEdits());
    const auto evidence = qEnvironmentVariable("AIBENCHIE_CANVAS_UI_SCREENSHOT");
    if (!evidence.isEmpty()) {
        auto *canvasDock = window.findChild<QDockWidget *>("canvasDock");
        for (auto *dock : window.findChildren<QDockWidget *>()) if (dock != canvasDock) dock->hide();
        window.removeDockWidget(canvasDock); window.addDockWidget(Qt::BottomDockWidgetArea, canvasDock);
        canvasDock->show(); window.resize(1280, 840); QCoreApplication::processEvents();
        ASSERT_TRUE(window.grab().save(evidence));
    }
    window.hide();
}
