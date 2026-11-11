// Fixture for Tier B symbols (Go).
package server

type Server struct{}

type Handler interface {
	Serve()
}

type (
	ID   int
	Name string
)

func New() *Server { return &Server{} }

func (s *Server) Start() {}

func helper() {
	local := func() {}
	_ = local
}
