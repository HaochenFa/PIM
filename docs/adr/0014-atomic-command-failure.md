# A failed command does not change the Working Collection

Invalid input is normal in a CLI. The process must not exit, must not print a traceback, and must not apply a subset of a bad command. The View shows one specific English error on the status line. Dirty state is unchanged. This makes requirements verifiable and matches the user-manual obligation to say what happens on invalid input.

**Status**: accepted
