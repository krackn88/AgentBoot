using System;
using System.Diagnostics;
using System.IO;

namespace OpenBullet.Linux.Services;

/// <summary>Plays WAV files on Linux via common CLI players (no Windows SoundPlayer).</summary>
public static class RunnerSoundPlayer
{
    public static void TryPlay(string relativePath)
    {
        if (string.IsNullOrWhiteSpace(relativePath)) return;

        var full = Path.IsPathRooted(relativePath)
            ? relativePath
            : Path.Combine(AppContext.BaseDirectory, relativePath);

        if (!File.Exists(full)) return;

        try
        {
            if (TrySpawn("paplay", full) || TrySpawn("aplay", full) || TrySpawn("ffplay", "-nodisp", "-autoexit", full))
                return;
        }
        catch
        {
            // optional feedback
        }
    }

    private static bool TrySpawn(string exe, params string[] args)
    {
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = exe,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            foreach (var a in args)
                psi.ArgumentList.Add(a);

            using var proc = Process.Start(psi);
            return proc != null;
        }
        catch
        {
            return false;
        }
    }
}
