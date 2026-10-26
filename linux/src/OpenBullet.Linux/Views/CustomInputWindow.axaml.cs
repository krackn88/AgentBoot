using Avalonia.Controls;
using Avalonia.Interactivity;

namespace OpenBullet.Linux.Views;

public partial class CustomInputWindow : Window
{
    public string Answer { get; private set; } = "";

    public CustomInputWindow()
    {
        InitializeComponent();
        AnswerBox.KeyDown += (_, e) =>
        {
            if (e.Key == Avalonia.Input.Key.Enter)
                OnOk(this, new RoutedEventArgs());
        };
    }

    public static CustomInputWindow Create(string prompt)
    {
        var w = new CustomInputWindow();
        w.PromptText.Text = prompt ?? "";
        return w;
    }

    private void OnOk(object sender, RoutedEventArgs e)
    {
        Answer = AnswerBox.Text ?? "";
        Close(true);
    }

    private void OnCancel(object sender, RoutedEventArgs e) => Close(false);
}
