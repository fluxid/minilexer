# -*- coding: utf-8 -*-

from logging import getLogger
import re

log = getLogger(__name__)

def one_iter(value):
    yield value

class Matcher:
    '''
    Base class for matchers
    '''
    def __init__(self):
        pass

    def match(self, context, line, pos):
        raise NotImplementedError

class MRE(Matcher):
    '''
    Regular expression matcher
    '''
    def __init__(self, regex, icase=False):
        super().__init__()

        flags = 0
        if icase:
            flags |= re.I

        self.regex = re.compile(regex, flags)

    def match(self, context, line, pos):
        match = self.regex.match(line, pos)
        if match:
            return len(match.group(0)), match
        return None

class MS(Matcher):
    '''
    Simple string matcher
    '''
    def __init__(self, string, icase=False):
        super().__init__()
        if icase:
            string = string.lower()
        self.icase = icase
        self.string = string

    def match(self, context, line, pos):
        tmp = line[pos:pos+len(self.string)]
        if self.icase:
            tmp = tmp.lower()

        if tmp == self.string:
            return len(self.string), self.string
        return None

class MM(Matcher):
    '''
    Multi matcher - tries given matchers in order
    '''
    def __init__(self, *args):
        self.args = args

    def match(self, context, line, pos):
        for arg in self.args:
            match = arg.match(context, line, pos)
            if match:
                return match
        return None

class LexerError(Exception):
    E_TOKEN_NOT_FOUND = 1
    E_MISSING_MATCH = 2
    E_MISSING_AFTER = 3
    E_LOOP = 4
    E_NO_MATCH = 5

    ID_TO_DESC = {
        E_TOKEN_NOT_FOUND: 'Token "{name}" not found.',
        E_MISSING_MATCH: 'Key "match" not found in token "{name}".',
        E_MISSING_AFTER: 'Key "after" not found in leaf token "{name}".',
        E_LOOP: 'Loop detected in lexer at "{name}".',
        E_NO_MATCH: (
            'Lexer error handler did not raise an error on unknown token. '
            'Also, unknown token found in line {lineno} at position {pos}.'
        ),
    }
    
    def __init__(self, error_id, **kwargs):
        self.error_id = error_id
        self.kwargs = kwargs

    def __str__(self):
        return self.ID_TO_DESC[self.error_id].format(**self.kwargs)

class BasicContext:
    def __init__(self, lexer):
        self.lexer = lexer

        self.current_line = None
        self.current_lineno = None
        self.current_pos = None

        self.token = None
        self.match = None

    def update_status(self, current_line, current_lineno, current_pos):
        self.current_line = current_line
        self.current_lineno = current_lineno
        self.current_pos = current_pos

        self.token = None
        self.match = None

    def token_match(self, token, match):
        self.token = token
        self.match = match

def iter_tokens(lexer, name):
    onpath = set()
    visited = set()

    stack = list()

    current_iter = one_iter(name)

    while True:
        name = next(current_iter, None)
        if name is None:
            if not stack:
                break
            name, current_iter = stack.pop()
            onpath.remove(name)
            continue

        token = lexer.get(name)
        if token is None:
            # token not found
            raise LexerError(LexerError.E_TOKEN_NOT_FOUND, name=name)

        match = token.get('match')
        if match is None:
            # token must have 'match' key
            raise LexerError(LexerError.E_MISSING_MATCH, name=name)

        if isinstance(match, Matcher):
            # It's leaf token
            if 'after' not in token: 
                # leaf token must have 'after' key
                raise LexerError(LexerError.E_MISSING_AFTER, name=name)
            yield name, token
            continue
        
        # it's not leaf token - it contains a list of tokens to try

        if name in onpath:
            # It's one of parents - so we would just loop endlessly. Raise an
            # error so we won't do this.
            raise LexerError(LexerError.E_LOOP, name=name)

        if name in visited:
            # We have already visited this token once - it's redundant, so we
            # ignore it without raising an error - it won't hurt.
            continue

        onpath.add(name)
        visited.add(name)

        stack.append((name, current_iter))
        current_iter = iter(match)

def parse(lexer, readline):
    begin = lexer['_begin']
    on_bad_token = lexer['_on_bad_token']
    context_class = lexer.get('_context_class', BasicContext)

    current_iter = None

    current_line = None
    current_lineno = 0
    current_pos = 0
    line_length = 0

    context = context_class(lexer)

    def reset_iter(lookup):
        nonlocal current_iter
        current_iter = iter_tokens(lexer, lookup)

    reset_iter(begin)

    while True:
        if current_pos >= line_length:
            current_line = readline()

            if not current_line:
                break

            current_lineno += 1
            current_pos = 0
            line_length = len(current_line)

        context.update_status(
            current_line,
            current_lineno,
            current_pos,
        )

        result = next(current_iter, None)
        if not result:
            on_bad_token(context)
            raise LexerError(LexerError.E_NO_MATCH, lineno=current_lineno, pos=current_pos+1)

        name, token = result
        matcher = token['match']
        after = token['after']

        match = matcher.match(context, current_line, current_pos)
        if match:
            length, match = match

        context.token_match(name, match)

        if match is None:
            on_fail = token.get('on_fail')
            if on_fail:
                on_fail(context)
            continue # I have no idea why this line shows up in coverage3 as missing...

        on_match = token.get('on_match')
        if on_match:
            on_match(context)

        log.debug('Matched: {} at line {} pos {} length {}'.format(name, current_lineno, current_pos+1, length))

        callme = getattr(after, '__call__', None)
        if callme:
            after = callme(context)

        current_pos += length
        reset_iter(after)

    return context
