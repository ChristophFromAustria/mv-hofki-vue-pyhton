\version "2.24.0"

%%%%%%%% PSEUDO-INDENT (inlined from pseudo-indent.ily) %%%%%%%%
% Source: https://wiki.lilypond.community/wiki/Indenting_individual_systems
pseudoIndents =
#(define-music-function (name-tweaks left-indent right-indent)
   ((markup-list? '()) number? number?)
   (define (warn-stretched p1 p2)
     (ly:input-warning (*location*) (G_ " \\pseudoIndents ~s ~s is stretching staff; expect distorted layout") p1 p2))
   (let*
       ((narrowing (+ left-indent right-indent))
        (set-staffsymbol!
         (lambda (staffsymbol-grob)
           (let* ((left-bound (ly:spanner-bound staffsymbol-grob LEFT))
                  (left-moment (ly:grob-property left-bound 'when))
                  (capo? (moment<=? left-moment ZERO-MOMENT))
                  (layout (ly:grob-layout staffsymbol-grob))
                  (lw (ly:output-def-lookup layout 'line-width))
                  (indent (ly:output-def-lookup layout (if capo? 'indent 'short-indent)))
                  (old-stil (ly:staff-symbol::print staffsymbol-grob))
                  (staffsymbol-x-ext (ly:stencil-extent old-stil X))
                  (ss-t (ly:staff-symbol-line-thickness staffsymbol-grob))
                  (pristine? (<= 0 (car staffsymbol-x-ext) ss-t))
                  (leftmost-x (+ indent (if pristine? 0 narrowing)))
                  (narrowing_ (if pristine? narrowing 0))
                  (old-width (+ (interval-length staffsymbol-x-ext) ss-t))
                  (new-width (- old-width narrowing_))
                  (new-rightmost-x (+ leftmost-x new-width))
                  (junk (ly:grob-set-property! staffsymbol-grob 'width new-rightmost-x))
                  (in-situ-stil (ly:staff-symbol::print staffsymbol-grob))
                  (new-stil (ly:stencil-translate-axis in-situ-stil narrowing_ X))
                  (new-x-ext (ly:stencil-extent new-stil X)))
             (ly:grob-set-property! staffsymbol-grob 'stencil new-stil)
             (ly:grob-set-property! staffsymbol-grob 'X-extent new-x-ext))))
        (set-X-offset!
         (lambda (margin-grob)
           (let* ((old (ly:grob-property-data margin-grob 'X-offset))
                  (new (lambda (grob) (+ (if (procedure? old) (old grob) old) narrowing))))
             (ly:grob-set-property! margin-grob 'X-offset new))))
        (tweak-text!
         (lambda (i-name-grob mkup)
           (when (and (markup? mkup) (not (string=? (markup->string mkup) "*")))
             (ly:grob-set-property! i-name-grob 'long-text mkup)
             (ly:grob-set-property! i-name-grob 'text mkup))))
        (install-narrowing
         (lambda (leftedge-grob)
           (let* ((sys (ly:grob-system leftedge-grob))
                  (all-grobs (ly:grob-array->list (ly:grob-object sys 'all-elements)))
                  (grobs-named (lambda (name) (filter (lambda (x) (eq? name (grob::name x))) all-grobs)))
                  (first-leftedge-grob (list-ref (grobs-named 'LeftEdge) 0))
                  (relsys-x-of (lambda (g) (ly:grob-relative-coordinate g sys X)))
                  (leftedge-x (relsys-x-of first-leftedge-grob))
                  (leftedged? (lambda (g) (= (relsys-x-of g) leftedge-x)))
                  (leftedged-ss (filter leftedged? (grobs-named 'StaffSymbol))))
             (when (eq? leftedge-grob first-leftedge-grob)
               (for-each set-staffsymbol! leftedged-ss)
               (for-each set-X-offset! (grobs-named 'SystemStartBar))
               (for-each set-X-offset! (grobs-named 'InstrumentName))
               (for-each tweak-text! (grobs-named 'InstrumentName) name-tweaks))))))
     (when (negative? narrowing) (warn-stretched left-indent right-indent))
     #{
       \break
       \once \override Score.LeftEdge.X-extent = #(cons narrowing narrowing)
       \once \override Score.LeftEdge.after-line-breaking = #install-narrowing
       \overrideProperty Score.NonMusicalPaperColumn .line-break-system-details .X-offset #(- right-indent)
       \once \override Score.BarNumber.horizon-padding = #(max 1 (- 1 narrowing))
     #}))
pseudoIndent =
#(define-music-function (name-tweaks left-indent) ((markup-list? '()) number?)
   #{ \pseudoIndents $name-tweaks $left-indent 0 #})
%%%%%%%% END PSEUDO-INDENT %%%%%%%%

#(set-default-paper-size "a5" 'landscape)

\paper {
  top-margin = 1
  bottom-margin = 4
  left-margin = 15
  right-margin = 15
  system-system-spacing.basic-distance = #5
  system-system-spacing.minimum-distance = #4
  system-system-spacing.padding = #0.2
  markup-system-spacing.basic-distance = #6
  top-system-spacing.basic-distance = #6
  last-bottom-spacing.basic-distance = #4
  indent = 0\mm
  short-indent = 0\mm
  bookTitleMarkup = \markup {
    \fill-line {
      ""
      \center-column {
        \fontsize #5 \bold \fromproperty #'header:title
        \fromproperty #'header:subtitle
      }
      \right-column {
        \fromproperty #'header:composer
        \fromproperty #'header:arranger
      }
    }
  }
}

\header {
  title = "Frisch auf! – Marsch"
  subtitle = "Basso I♭"
  composer = "Robert Pensch"
  arranger = "arr.: Hans Kliment jr."
  tagline = ##f
}

% Haltebogen (tie): note~ note  z.B. bes,2~ bes,2

\score {
  \new Staff {
    \set Staff.instrumentName = ""
    \set Staff.shortInstrumentName = ""
    \clef bass
    \key bes \major
    \time 2/2

    %% System 1: Einleitung + 1. Strain Anfang
    \compressMMRests { \once \override MultiMeasureRestNumber.direction = #DOWN R1*2 } ees4\f r f2( | bes,4) r r2 | \bar ".|:" \repeat volta 2 { bes,4->\f r f,4-.\p r | bes,4-. r f,4-. r | bes,4-. r f,4-. r | c4-.\< r f2 | f,4 r a,4\! r | c4-. r f4-. r | bes,4-.\mf r bes,4-. r |
    \break

    %% System 2: 1. Strain Fortsetzung + Wiederholung
     f4-.\< ees4-> d4-> c4->\! | bes,4->\f r f,4-. r | bes,4-. r f,4-. r | bes,4-. r f,4-. r |  c4 r r2 |  c4-.->\ff r8 c8 c2-- | f,4-.-> r8 a,!8 a,2-- | g,4-. r4 c2(  | f4) r4 r2   } 
    \break

    %% System 3: 2. Strain
    \repeat volta 2 { c4-.-> \f r4 r2 | f,4-.\mf r f,4-. r | bes,4-. r f,4-. r | bes,4-. r r bes,4-.\f | a,!2-> bes,2-> | c4-> a,!4-> g,4-> f,4-> | bes,2-> c2-> | d4 r bes,2(\< | c4->) r\! r2 |
    \break

    %% System 4: 2. Strain Fortsetzung + 1./2. Ending
    f4-.\mf r f4-. r | bes,4-. r f4-. r | bes,4-. r r bes,4\f | ees4 r e2-> | f4-. r f2-> | f4-. r f,2( | } \alternative { \volta 1 { d4)-> r r2 | } \volta 2 { bes,4-. bes,8 bes,8 bes,4-. r4} } \bar "||"

    %% System 5: Trio Einleitung + Trio body Anfang
    \key ees \major \pseudoIndent \markuplist { \fontsize #5 \bold "Trio" } 8 ees4\f r4 \mf\> \tuplet 3/2 { ees,4 g,4 bes,4 \!} | ees4 r4 r2  \repeat volta 2 { ees4\p r4 bes,4 r4 | ees4 r4 bes,4 r4 | ees4 r bes,4 r | ees4 r\< bes,4 r | ees4 r\! d4 r | 

    %% System 6: Trio body Fortsetzung
    \set Staff.instrumentName = ##f \break f4\mf r bes,4 r | f4 r bes,4 r | f4 r bes,4 r | f4 r bes,4 r | f4 r bes,4 r | f4\< r bes,4 r | f4 r d4 r\! | d4-> r bes,4 r | d4-> r bes,4 r |
    \break

    %% System 7: Schluss
    ees4-.\< ees4-. d4-. c4-. | bes,4-. a,4-. g,4-. f,4-. | f,4\!\f r bes,4 r | ees4-> r bes,4 r | ees4-> r bes,4 r | ees4-> r bes,4 r | ees4-> r bes,4 r | ees4 r ees4 r | aes,2.-- r4 | aes,2.-- r4 |
    \break

    %% System 8: Schluss Wiederholung
     a,1->\ff | a,1-> | ees4-. r bes,4-. r | ees4-. r bes,4-. r | ees4-. r bes,4-. r | ees4-. r bes,4-. r | } \alternative { \volta 1 { ees4 r8 c8(\> bes,4-.) g,4-. | ees,4-. r4\! r2 | } \volta 2 { ees4 r8 c8(\> bes,4-.) g,4-. | ees,4-. r4\! ees4-.->\ff r4 | } } \bar "|."
  }
  \layout {
    #(layout-set-staff-size 17)
    \context {
      \Score
      \override SpacingSpanner.common-shortest-duration = #(ly:make-moment 1/4)
      \override SpacingSpanner.spacing-increment = #1.0
      \omit BarNumber
    }
  }
  \midi { \tempo 2 = 120 }
}
