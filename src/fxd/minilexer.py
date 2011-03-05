# -*- coding: utf-8 -*-

# fxd.minilexer - Simple lexer for Python 3
# Copyright (c) 2011 Tomasz Kowalczyk
# Contact e-mail: code@fluxid.pl
#
# This library is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
# 
# This library is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
# details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this library in the file COPYING.LESSER. If not, see
# <http://www.gnu.org/licenses/>.

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

    def match(self, parser, line, pos):
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

    def match(self, parser, line, pos):
        match = self.regex.match(line, pos)
        if match:
            return pos + len(match.group(0)), match
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

    def match(self, parser, line, pos):
        tmp = line[pos:pos+len(self.string)]
        if self.icase:
            tmp = tmp.lower()

        if tmp == self.string:
            return pos + len(self.string), self.string
        return None

class MM(Matcher):
    '''
    Multi matcher - tries given matchers in order
    '''
    def __init__(self, *args):
        self.args = args

    def match(self, parser, line, pos):
        for arg in self.args:
            parser.cache_push()
            match = arg.match(parser, line, pos)
            if match:
                return match
            parser.cache_pop()
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

class Parser:
    def __init__(self, lexer, eol_newline = False):
        self.lexer = lexer
        self.eol_newline = eol_newline

        self.current_readline = None
        self.line_cache = list()
        self.idx_stack = list()
        self.next_lineidx = 0

        self.current_iter = None
        self.current_line = ''
        self.current_lineno = 0
        self.current_pos = 0

        self.reset_iter(lexer['_begin'])

    def parse_readline(self, readline):
        self.current_readline = readline
        self.run_parser()

    def parse_lines(self, lines):
        iterator = iter(lines)
        def iterating_readline():
            try:
                return next(iterator)
            except StopIteration:
                return ''
        self.parse_readline(iterating_readline)

    def readline(self):
        if self.next_lineidx >= len(self.line_cache) and self.current_readline:
            line = self.current_readline()
            if line:
                splitted = line.splitlines()
                if self.eol_newline:
                    splitted = (
                        l + '\n'
                        for l in splitted
                    )
                self.line_cache.extend(splitted)
            else:
                self.current_readline = None

        line = ''
        if self.next_lineidx < len(self.line_cache):
            line = self.line_cache[self.next_lineidx]
            self.next_lineidx += 1
            self.current_lineno += 1
            self.current_pos = 0
            self.current_line = line
        return line
    
    def cache_push(self):
        self.idx_stack.append((
            self.next_lineidx,
            self.current_lineno,
            self.current_pos,
            self.current_line,
        ))

    def cache_pop(self):
        if self.idx_stack:
            (
                self.next_lineidx,
                self.current_lineno,
                self.current_pos,
                self.current_line,
            ) = self.idx_stack.pop()

    def cache_discard(self):
        if self.idx_stack:
            del self.idx_stack[-1]

    def cache_purge(self):
        if self.idx_stack:
            del self.idx_stack[:]
        if self.line_cache:
            del self.line_cache[:self.next_lineidx]
            self.next_lineidx = 0

    def iter_tokens(self, name):
        onpath = set()
        visited = set()

        stack = list()

        token_iter = one_iter(name)

        while True:
            name = next(token_iter, None)
            if name is None:
                if not stack:
                    break
                name, token_iter = stack.pop()
                onpath.remove(name)
                continue

            token = self.lexer.get(name)
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

            stack.append((name, token_iter))
            token_iter = iter(match)

    def reset_iter(self, lookup):
        self.current_iter = self.iter_tokens(lookup)

    def on_bad_token(self):
        raise LexerError(LexerError.E_NO_MATCH, lineno=self.current_lineno, pos=self.current_pos+1)

    def token_match(self, token, match):
        log.debug('Matched: {} at line {} pos {}'.format(token, self.current_lineno, self.current_pos+1))

    def run_parser(self):
        while True:
            if self.current_pos >= len(self.current_line) and not self.readline():
                break

            result = next(self.current_iter, None)
            if not result:
                self.on_bad_token()
                break

            name, token = result
            matcher = token['match']
            after = token['after']
 
            self.cache_push()

            match = matcher.match(self, self.current_line, self.current_pos)
            if match:
                new_pos, match = match

            if match is None:
                self.cache_pop()
                on_fail = token.get('on_fail')
                if on_fail:
                    on_fail(self)
                continue

            self.token_match(name, match)

            on_match = token.get('on_match')
            if on_match:
                on_match(self)

            callme = getattr(after, '__call__', None)
            if callme:
                after = callme(self)

            self.current_pos = new_pos
            self.reset_iter(after)
            self.cache_purge()
